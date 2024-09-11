# Copyright 2023 by Garmin Ltd. or its subsidiaries
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import enum
import logging
import os
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import attr
import httpx
import service
import uci
from labgrid import step, target_factory
from labgrid.driver import QEMUDriver, ShellDriver, SSHDriver
from labgrid.strategy import Strategy, StrategyError
from labgrid.util import get_free_port


class Status(enum.Enum):
    unknown = 0
    off = 1
    shell = 2


@target_factory.reg_driver
@attr.s(eq=False)
class QEMUNetworkStrategy(Strategy):
    bindings = {
        "qemu": "QEMUDriver",
        "shell": "ShellDriver",
        "ssh": "SSHDriver",
    }

    qemu: Optional[QEMUDriver] = None
    shell: Optional[ShellDriver] = None
    ssh: Optional[SSHDriver] = None

    status = attr.ib(default=Status.unknown)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        assert self.ssh

        self._download_image()  # keep .gz image
        self._extract_image()  # overwrite image if existing

        self.__port_forward = None
        self.__remote_port = self.ssh.networkservice.port

    @property
    def disk_url(self) -> str:
        return self.target.env.config.data["urls"]["disk-image"]

    @property
    def disk_path(self) -> Path:
        if not self.qemu.disk:
            raise NotImplementedError(
                "Disk image has not been configured for QEMUDriver."
            )
        return Path(self.target.env.config.get_image_path(self.qemu.disk)).resolve()

    @property
    def compressed_disk_path(self) -> Path:
        return self.disk_path.parent / os.path.basename(
            urllib.parse.urlparse(self.disk_url).path
        )

    @step()
    def _download_image(self) -> None:
        if self.compressed_disk_path.exists():
            logging.info(
                f"Image {self.compressed_disk_path} already exists. Skipping download."
            )
            return
        response = httpx.get(self.disk_url)
        response.raise_for_status()
        self.compressed_disk_path.write_bytes(response.content)

    @step()
    def _extract_image(self) -> None:
        # using gunzip to extract the image as it is more robust than Python's built-in gzip module
        logging.info(
            f"Extracting {self.compressed_disk_path.name} to {self.disk_path.name}."
        )
        with open(self.disk_path, "wb") as output_file:
            gunzip_process = subprocess.Popen(
                ["gunzip"],
                stdin=subprocess.PIPE,
                stdout=output_file,
                stderr=subprocess.PIPE,
            )

            assert gunzip_process.stdin
            gunzip_process.stdin.write(self.compressed_disk_path.read_bytes())
            gunzip_process.stdin.close()

            gunzip_process.wait()

    @step(result=True)
    def get_remote_address(self):
        return str(self.shell.get_ip_addresses()[0].ip)

    @step()
    def update_network_service(self):
        if not "accel kvm" in self.qemu.extra_args:
            time.sleep(5)  # wait for device to acquire IP address
        new_address = self.get_remote_address()
        networkservice = self.ssh.networkservice

        if networkservice.address != new_address:
            self.target.deactivate(self.ssh)

            if "user" in self.qemu.nic.split(","):
                if self.__port_forward is not None:
                    self.qemu.remove_port_forward(*self.__port_forward)

                local_port = get_free_port()
                local_address = "127.0.0.1"

                self.qemu.add_port_forward(
                    "tcp",
                    local_address,
                    local_port,
                    new_address,
                    self.__remote_port,
                )
                self.__port_forward = ("tcp", local_address, local_port)

                networkservice.address = local_address
                networkservice.port = local_port
            else:
                networkservice.address = new_address
                networkservice.port = self.__remote_port

    @step(args=["state"])
    def transition(self, state, *, step):
        if not isinstance(state, Status):
            state = Status[state]

        if state == Status.unknown:
            raise StrategyError(f"can not transition to {state}")

        elif self.status == state:
            step.skip("nothing to do")
            return

        if state == Status.off:
            assert self.target
            self.target.activate(self.qemu)
            assert self.qemu
            self.qemu.off()

        elif state == Status.shell:
            assert self.target
            self.target.activate(self.qemu)
            assert self.qemu
            self.qemu.on()
            self.target.activate(self.shell)
            assert self.shell

            uci.set(self.shell, "network.lan.proto", "dhcp")
            uci.commit(self.shell, "network")
            service.restart(self.shell, "network", wait=1)
            self.update_network_service()

        self.status = state
