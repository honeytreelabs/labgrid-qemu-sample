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
import subprocess
import time
from pathlib import Path
from typing import Optional

import attr
import requests
from labgrid import step, target_factory
from labgrid.driver import QEMUDriver, ShellDriver, SSHDriver
from labgrid.strategy import Strategy, StrategyError
from labgrid.util import get_free_port
from process import run


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

        self._download_image()

        self.__port_forward = None
        self.__remote_port = self.ssh.networkservice.port

    @step()
    def _download_image(self) -> None:
        url = self.target.env.config.data["urls"]["disk-image"]
        if not self.qemu.disk:
            raise NotImplementedError(
                "Disk image has not been configured for QEMUDriver."
            )
        disk_path = Path(self.target.env.config.get_image_path(self.qemu.disk))
        if disk_path.exists():
            return
        response = requests.get(url)
        response.raise_for_status()
        # using gunzip to extract the image as it is more robust than Python's built-in gzip module
        with open(disk_path, "wb") as output_file:
            # Create a subprocess for gunzip
            gunzip_process = subprocess.Popen(
                ["gunzip"],
                stdin=subprocess.PIPE,
                stdout=output_file,
                stderr=subprocess.PIPE,
            )

            # Send the response content to the gunzip process's stdin
            gunzip_process.stdin.write(response.content)
            gunzip_process.stdin.close()

            # Wait for the gunzip process to complete
            gunzip_process.wait()

    @step(result=True)
    def get_remote_address(self):
        return str(self.shell.get_ip_addresses()[0].ip)

    @step()
    def update_network_service(self):
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
            run(self.shell, "uci set network.lan.proto=dhcp")
            run(self.shell, "uci commit network")
            run(self.shell, "/etc/init.d/network restart")
            time.sleep(1)
            self.update_network_service()

        self.status = state
