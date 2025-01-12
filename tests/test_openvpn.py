import logging
from collections.abc import Iterator
from pathlib import Path

import openwrt
import pytest
from docker import DockerComposeWrapper
from labgrid.driver import SSHDriver
from network import NetworkError, primary_host_ip, resolve
from process import run
from ssh import put_file
from x509 import PKI, create_pki

OPENVPN_DIR = Path(__file__).parent / "openvpn"


@pytest.fixture(scope="module")
def pki() -> PKI:
    return create_pki()


@pytest.fixture(scope="module")
def openvpn_server_env(pki: PKI) -> Iterator[DockerComposeWrapper]:
    compose = DockerComposeWrapper(
        (OPENVPN_DIR / "compose.yaml").read_text(),
        {
            "ca_cert.pem": pki.ca_cert,
            "server_key.pem": pki.server_key,
            "server_cert.pem": pki.server_cert,
            "client_key.pem": pki.client_key,
            "client_cert.pem": pki.client_cert,
            "Dockerfile.openvpn": (OPENVPN_DIR / "Dockerfile.openvpn").read_bytes(),
        },
    )
    compose.up(build=True)
    yield compose
    compose.rm(force=True, stop=True)


@pytest.mark.openvpn
def test_openvpn(pki: PKI, openvpn_server_env: DockerComposeWrapper, ssh_command: SSHDriver) -> None:
    def step_openwrt_install_openvpn() -> None:
        if "openvpn-openssl" not in run(ssh_command, "opkg list-installed"):
            run(ssh_command, "opkg update")
            run(ssh_command, "opkg install openvpn-openssl")
            run(ssh_command, "sync")

    def step_openwrt_setup_openvpn() -> None:
        run(ssh_command, "mkdir -p /etc/openvpn")
        put_file(ssh_command, Path("/etc") / "openvpn" / "ca.crt", pki.ca_cert)
        put_file(ssh_command, Path("/etc") / "openvpn" / "client.crt", pki.client_cert)
        put_file(ssh_command, Path("/etc") / "openvpn" / "client.key", pki.client_key)
        run(ssh_command, "uci set openvpn.sample_client.enabled='1'")
        try:
            openvpn_server_ip = resolve("openvpn-server")
        except NetworkError:
            logging.info("Could not resolve openvpn-server address. Trying published port on host.")
            openvpn_server_ip = primary_host_ip()
        run(ssh_command, f"uci set openvpn.sample_client.remote='{openvpn_server_ip} 1194'")
        run(ssh_command, "uci commit openvpn")
        run(ssh_command, "/etc/init.d/openvpn restart sample_client")

    def step_openwrt_configure_firewall() -> None:
        run(ssh_command, 'uci add_list firewall.@zone[0].device="tun0"')
        run(ssh_command, "uci commit firewall")
        run(ssh_command, "service firewall restart")

    def step_verify_connected() -> None:
        assert run(ssh_command, "ping -c 5 192.168.123.1")
        tun0_ips = openwrt.get_ip_addr(ssh_command, "tun0")
        assert len(tun0_ips) == 1
        assert openvpn_server_env.exec("openvpn-server", f"ping -c 5 {tun0_ips[0]}")

    step_openwrt_install_openvpn()
    step_openwrt_setup_openvpn()
    step_openwrt_configure_firewall()
    step_verify_connected()
