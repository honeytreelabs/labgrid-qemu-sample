import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml
from fs import create_temp_dir
from network import NetworkError, get_free_tcp_port, get_free_udp_port, primary_host_ip, resolve


def in_docker_container() -> bool:
    return Path("/.dockerenv").exists()


PortMappings = dict[str, dict[str, int]]


class ComposeRenderer:
    def __init__(self, compose_template: str) -> None:
        self._compose_data: dict = yaml.safe_load(compose_template)
        self._port_mappings: PortMappings = {"tcp": {}, "udp": {}}

    @property
    def rendered(self) -> str:
        return yaml.dump(self._compose_data, default_flow_style=False)

    @property
    def port_mappings(self) -> PortMappings:
        return self._port_mappings

    def map_service(self, hostname: str) -> str:
        del hostname  # unused
        raise NotImplementedError()


class LocalComposeRenderer(ComposeRenderer):
    def __init__(self, compose_template: str) -> None:
        super().__init__(compose_template)
        services = self._compose_data.get("services", {})
        for _, service_data in services.items():
            networks = service_data.get("networks", [])
            if networks:
                service_data["networks"] = [network for network in networks if network != "shared_network"]

            ports: list[str] = service_data.get("ports", [])
            for idx, port in enumerate(ports):
                match = DOCKER_PORT_REGEX.match(port)
                if match:
                    name = match.group(1)
                    port = int(match.group(2))
                    proto = match.group(4)
                    proto_str = proto if proto else "tcp"
                    free_port = get_free_udp_port() if proto else get_free_tcp_port()
                    self._port_mappings[proto_str][name] = free_port
                    ports[idx] = f"{free_port}:{port}/{proto_str}"
                else:
                    logging.warning(f"Could not parse port expression {port}")

    def map_service(self, hostname: str) -> str:
        del hostname  # unused
        return str(primary_host_ip())


DOCKER_PORT_REGEX: re.Pattern = re.compile(
    r"\{([\w-]+)\}:(\d+)(/((tcp)|(udp)))?",
    flags=re.DOTALL | re.IGNORECASE,
)


class DockerInDockerComposeRenderer(ComposeRenderer):
    def __init__(self, compose_template: str) -> None:
        super().__init__(compose_template)
        services = self._compose_data.get("services", {})
        for service_name, service_data in services.items():
            if "volumes" in service_data:
                logging.info(
                    "Volume mounts are not supported in docker-in-docker scenarios. "
                    f"Some have been found in the {service_name} service."
                )

            ports: list[str] = service_data.get("ports", [])
            for idx, port in enumerate(ports):
                match = DOCKER_PORT_REGEX.match(port)
                if match:
                    name = match.group(1)
                    port = int(match.group(2))
                    proto = match.group(4)
                    proto_str = proto if proto else "tcp"
                    self._port_mappings[proto_str][name] = port
                    ports[idx] = f"{port}:{port}/{proto_str}"
                else:
                    logging.warning(f"Could not parse port expression {port}")

    def map_service(self, hostname: str) -> str:
        try:
            return str(resolve(hostname))
        except NetworkError:
            logging.info("Could not resolve openvpn-server address. Trying published port on host.")
            return str(primary_host_ip())


def create_compose_renderer(compose_template: str) -> ComposeRenderer:
    if in_docker_container():
        return DockerInDockerComposeRenderer(compose_template)
    return LocalComposeRenderer(compose_template)


class DockerComposeWrapper:
    def __init__(self, compose_template: str, files: dict[str, bytes]) -> None:
        self._tmpdir = create_temp_dir()
        self._compose = create_compose_renderer(compose_template)
        logging.info(f"Rendered compose YAML:\n{self._compose.rendered}")
        (Path(self._tmpdir) / "compose.yaml").write_text(
            self._compose.rendered,
        )
        for filename, contents in files.items():
            (Path(self._tmpdir) / filename).write_bytes(contents)

    @property
    def cwd(self) -> Path:
        return self._tmpdir

    @property
    def port_mappings(self) -> PortMappings:
        return self._compose.port_mappings

    def map_hostname(self, hostname: str) -> str:
        return self._compose.map_service(hostname)

    def _run_command(self, *args: str) -> str:
        command = ["docker", "compose"] + list(args)
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

    def cleanup(self) -> None:
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
