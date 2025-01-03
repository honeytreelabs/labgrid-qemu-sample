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

import logging
import os
import subprocess
import urllib.parse
from pathlib import Path

import attr
import httpx
from labgrid import step, target_factory

from .qemu_strategy import QEMUBaseStrategy


@target_factory.reg_driver
@attr.s(eq=False)
class QEMUNetworkStrategy(QEMUBaseStrategy):
    bindings = {
        "qemu": "CustomQEMUDriver",
        "shell": "ShellDriver",
        "ssh": "SSHDriver",
        "params": "QEMUParams",
    }

    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        assert self.params

        self._download_image()  # keep .gz image
        if self.params.overwrite:
            logging.info(f"Overwriting image {self.disk_path}")
            self._extract_image()  # overwrite image if existing

    def on(self) -> None:
        self.qemu.on()  # type: ignore

    def off(self) -> None:
        self.qemu.off()  # type: ignore

    @property
    def disk_url(self) -> str:
        return self.target.env.config.data["urls"]["disk-image"]

    @property
    def disk_path(self) -> Path:
        if not self.qemu.disk:
            raise NotImplementedError("Disk image has not been configured for QEMUDriver.")
        return Path(self.target.env.config.get_image_path(self.qemu.disk)).resolve()

    @property
    def compressed_disk_path(self) -> Path:
        return self.disk_path.parent / os.path.basename(urllib.parse.urlparse(self.disk_url).path)

    @step()
    def _download_image(self) -> None:
        if self.compressed_disk_path.exists():
            logging.info(f"Image {self.compressed_disk_path} already exists. Skipping download.")
            return
        response = httpx.get(self.disk_url)
        response.raise_for_status()
        self.compressed_disk_path.write_bytes(response.content)

    @step()
    def _extract_image(self) -> None:
        # using gunzip to extract the image as it is more robust than Python's built-in gzip module
        logging.info(f"Extracting {self.compressed_disk_path.name} to {self.disk_path.name}.")
        with open(self.disk_path, "wb") as output_file:
            gunzip_process = subprocess.Popen(
                ["/usr/bin/gunzip"],
                stdin=subprocess.PIPE,
                stdout=output_file,
                stderr=subprocess.PIPE,
            )

            assert gunzip_process.stdin
            gunzip_process.stdin.write(self.compressed_disk_path.read_bytes())
            gunzip_process.stdin.close()

            gunzip_process.wait()
