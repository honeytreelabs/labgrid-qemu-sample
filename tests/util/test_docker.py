import logging
from ipaddress import IPv4Address
from pathlib import Path
from unittest.mock import MagicMock, patch

from docker import DockerComposeWrapper, DockerInDockerComposeRenderer, LocalComposeRenderer

OPENVPN_COMPOSE_TEMPLATE: str = (Path(__file__).parent.parent / "openvpn" / "compose.yaml").read_text()


@patch("docker.in_docker_container")
def test_docker_compose_env_ok(in_docker_container: MagicMock) -> None:
    in_docker_container.return_value = True
    docker_compose_wrapper = DockerComposeWrapper(OPENVPN_COMPOSE_TEMPLATE, {})
    logging.info(f"Current Docker Compose Env Dir: {docker_compose_wrapper.cwd}")


@patch("docker.primary_host_ip")
@patch("docker.in_docker_container")
def test_docker_compose_renderer_local(in_docker_container: MagicMock, primary_host_ip: MagicMock) -> None:
    primary_host_ip.return_value = IPv4Address("1.2.3.4")
    in_docker_container.return_value = False

    renderer = LocalComposeRenderer(OPENVPN_COMPOSE_TEMPLATE)
    assert not renderer.port_mappings["tcp"]
    assert len(renderer.port_mappings["udp"]) == 1  # openvpn port
    assert renderer.map_service("openvpn-server") == IPv4Address("1.2.3.4")


@patch("docker.resolve")
@patch("docker.in_docker_container")
def test_docker_compose_renderer_dind(in_docker_container: MagicMock, resolve: MagicMock) -> None:
    resolve.return_value = IPv4Address("5.6.7.8")
    in_docker_container.return_value = True

    renderer = DockerInDockerComposeRenderer(OPENVPN_COMPOSE_TEMPLATE)
    assert renderer.port_mappings["udp"]["openvpn"] == 1194
    assert renderer.map_service("openvpn-server") == IPv4Address("5.6.7.8")
