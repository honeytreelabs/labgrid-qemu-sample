import logging
import tempfile
from ipaddress import IPv4Address
from pathlib import Path
from typing import Iterator

import pytest
from docker import DockerComposeWrapper
from labgrid.driver import SSHDriver
from process import run
from x509 import PKI, create_pki

OPENVPN_DIR = Path(__file__).parent / "openvpn"


@pytest.fixture
def generated_pki() -> PKI:
    pki = create_pki()
    (OPENVPN_DIR / "ca_cert.pem").write_bytes(pki.ca_cert)
    (OPENVPN_DIR / "server_key.pem").write_bytes(pki.server_key)
    (OPENVPN_DIR / "server_cert.pem").write_bytes(pki.server_cert)
    (OPENVPN_DIR / "client_key.pem").write_bytes(pki.client_key)
    (OPENVPN_DIR / "client_cert.pem").write_bytes(pki.client_cert)
    return pki


@pytest.fixture
def install_openvpn_client(ssh_command: SSHDriver) -> None:
    run(ssh_command, "opkg update")
    run(ssh_command, "opkg install openvpn-openssl")


@pytest.fixture
def openvpn_client(
    ssh_command: SSHDriver,
    install_openvpn_client: None,
    generated_pki: PKI,
    primary_host_ip: IPv4Address,
) -> None:
    del install_openvpn_client  # unused
    del generated_pki  # unused

    run(ssh_command, "mkdir -p /etc/openvpn")
    ssh_command.put(str(OPENVPN_DIR / "ca_cert.pem"), "/etc/openvpn/ca.crt")
    ssh_command.put(str(OPENVPN_DIR / "client_cert.pem"), "/etc/openvpn/client.crt")
    ssh_command.put(str(OPENVPN_DIR / "client_key.pem"), "/etc/openvpn/client.key")
    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        temp_file.write(
            (OPENVPN_DIR / "client.conf.tmpl")
            .read_text()
            .format(server_ip=primary_host_ip)
            .encode("utf-8")
        )
        temp_file.flush()
        ssh_command.put(temp_file.name, "/etc/openvpn/client.conf")
    run(ssh_command, "service openvpn restart")


@pytest.fixture
def openvpn_server_env(generated_pki: PKI) -> Iterator[DockerComposeWrapper]:
    del generated_pki  # unused

    compose = DockerComposeWrapper(Path(__file__).parent / "openvpn" / "compose.yaml")
    compose.up()
    yield compose
    compose.rm(force=True, stop=True)


def test_openvpn(
    ssh_command: SSHDriver,
    openvpn_client: None,
    openvpn_server_env: DockerComposeWrapper,
) -> None:
    del openvpn_client  # unused
    logging.info(openvpn_server_env.exec("openvpn-server", "ps faux"))
    assert len(openvpn_server_env.ps()) == 1
    assert run(ssh_command, "ping -c 5 172.87.0.1")
