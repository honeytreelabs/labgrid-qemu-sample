from pathlib import Path
from typing import Iterator

import openwrt
import pytest
from docker import DockerComposeWrapper
from labgrid.driver import SSHDriver
from network import primary_host_ip
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
def openvpn_server_env(generated_pki: PKI) -> Iterator[DockerComposeWrapper]:
    del generated_pki  # unused

    compose = DockerComposeWrapper(OPENVPN_DIR / "compose.yaml")
    compose.up()
    yield compose
    compose.rm(force=True, stop=True)


def test_openvpn(
    ssh_command: SSHDriver,
    openvpn_server_env: DockerComposeWrapper,
) -> None:
    def step_openwrt_install_openvpn() -> None:
        run(ssh_command, "opkg update")
        run(ssh_command, "opkg install openvpn-openssl")

    def step_openwrt_setup_openvpn() -> None:
        run(ssh_command, "mkdir -p /etc/openvpn")
        ssh_command.put(str(OPENVPN_DIR / "ca_cert.pem"), "/etc/openvpn/ca.crt")
        ssh_command.put(str(OPENVPN_DIR / "client_cert.pem"), "/etc/openvpn/client.crt")
        ssh_command.put(str(OPENVPN_DIR / "client_key.pem"), "/etc/openvpn/client.key")
        run(ssh_command, "uci set openvpn.sample_client.enabled='1'")
        run(ssh_command, f"uci set openvpn.sample_client.remote='{primary_host_ip()} 1194'")
        run(ssh_command, "uci commit openvpn")
        run(ssh_command, "/etc/init.d/openvpn start sample_client")

    def step_openwrt_configure_firewall() -> None:
        run(ssh_command, 'uci add_list firewall.@zone[0].device="tun0"')
        run(ssh_command, "uci commit firewall")
        run(ssh_command, "service firewall restart")

    def step_verify_connected() -> None:
        assert run(ssh_command, "ping -c 5 172.17.0.1")
        tun0_ip = openwrt.get_ip_addr(ssh_command, "tun0")
        assert openvpn_server_env.exec("openvpn-server", f"ping -c 5 {tun0_ip}")

    step_openwrt_install_openvpn()
    step_openwrt_setup_openvpn()
    step_openwrt_configure_firewall()
    step_verify_connected()
