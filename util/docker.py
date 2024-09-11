import json
import subprocess
from pathlib import Path
from typing import Any, List, Optional


class DockerComposeWrapper:
    def __init__(self, compose_file: Path = Path("compose.yaml")) -> None:
        self.compose_file = compose_file

    def _run_command(self, *args: str) -> str:
        command = ["docker", "compose", "-f", self.compose_file] + list(args)
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout

    def up(self, detach: bool = True) -> None:
        args = ["up"]
        if detach:
            args.append("-d")
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
        user: Optional[str] = None,
    ) -> str:
        args = ["exec"]
        if detach:
            args.append("-d")
        if user:
            args += ["-u", user]
        args += [service] + command.split()
        return self._run_command(*args)

    def kill(self, service: Optional[str] = None, signal: Optional[str] = None) -> None:
        args = ["kill"]
        if signal:
            args += ["-s", signal]
        if service:
            args.append(service)
        self._run_command(*args)

    def ps(self, services: Optional[List[str]] = None) -> list[dict[str, Any]]:
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
