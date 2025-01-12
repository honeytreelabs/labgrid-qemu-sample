import json
import logging
import random
import shutil
import string
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def create_temp_dir() -> Path:
    while True:
        # we don't need a super-secure cryptographic PRNG
        random_name = "".join(random.choices(string.ascii_letters + string.digits, k=12))  # noqa: S311
        temp_path = Path(tempfile.gettempdir()) / random_name
        logging.info(f"Creating temporary directory {temp_path}.")
        try:
            temp_path.mkdir(exist_ok=False)
            return temp_path
        except FileExistsError:
            continue


class DockerComposeWrapper:
    def __init__(self, compose_yaml: str, files: dict[str, bytes]) -> None:
        self._tmpdir = create_temp_dir()
        self.compose_file = Path(self._tmpdir) / "compose.yaml"
        self.compose_file.write_text(compose_yaml)
        for filename, contents in files.items():
            (Path(self._tmpdir) / filename).write_bytes(contents)

    def _run_command(self, *args: str) -> str:
        command = ["docker", "compose", "-f", self.compose_file] + list(args)
        result = subprocess.run(
            command,
            cwd=self._tmpdir,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def up(self, detach: bool = True, build: bool = False) -> None:
        args = ["up"]
        if detach:
            args.append("-d")
        if build:
            args.append("--build")
        self._run_command(*args)

    def rm(self, force: bool = False, stop: bool = False, volumes: bool = False) -> None:
        args = ["rm"]
        if force:
            args.append("-f")
        if stop:
            args.append("-s")
        if volumes:
            args.append("-v")
        self._run_command(*args)

    def exec(
        self,
        service: str,
        command: str,
        detach: bool = False,
        user: str | None = None,
    ) -> str:
        args = ["exec"]
        if detach:
            args.append("-d")
        if user:
            args += ["-u", user]
        args += [service] + command.split()
        return self._run_command(*args)

    def kill(self, service: str | None = None, signal: str | None = None) -> None:
        args = ["kill"]
        if signal:
            args += ["-s", signal]
        if service:
            args.append(service)
        self._run_command(*args)
        shutil.rmtree(self._tmpdir)

    def ps(self, services: list[str] | None = None) -> list[dict[str, Any]]:
        args = ["ps", "--format=json"]
        if services:
            args += services
        raw = self._run_command(*args)
        try:
            return json.loads(f"[{raw}]")
        except json.decoder.JSONDecodeError:
            # see: https://github.com/docker/compose/issues/10958
            comma_separated = ",".join(raw.strip().split("\n"))
            return json.loads(f"[{comma_separated}]")
