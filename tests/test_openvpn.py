from ipaddress import IPv4Address
from pathlib import Path

import openwrt
import opkg
import pytest
import service
import uci
from docker import ComposeAdapter, ComposeEnv, ComposeEnvFactory
from fs import mkdir, sync
from labgrid.driver import SSHDriver
from process import run
from ssh import put_file
from x509 import PKI, create_pki

OPENVPN_DIR = Path(__file__).parent / "openvpn"


@pytest.fixture(scope="module")
def pki() -> PKI:
    return create_pki(ComposeAdapter.map_service("openvpn-server"))


@pytest.fixture(scope="module")
def openvpn_server_env(compose_env_factory: ComposeEnvFactory, pki: PKI) -> ComposeEnv:
    return compose_env_factory(
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


@pytest.fixture(scope="module")
def openvpn_server_name(openvpn_server_env: ComposeEnv) -> str | IPv4Address:
    return openvpn_server_env.map_hostname("openvpn-server")


@pytest.fixture(scope="module")
def openvpn_server_port(openvpn_server_env: ComposeEnv) -> int:
    return openvpn_server_env.port_mappings["udp"]["openvpn"]


@pytest.mark.openvpn
def test_openvpn(
    pki: PKI,
    openvpn_server_env: ComposeEnv,
    openvpn_server_name: str | IPv4Address,
    openvpn_server_port: int,
    ssh_command: SSHDriver,
) -> None:
    def step_openwrt_install_openvpn() -> None:
        if not opkg.is_package_installed(ssh_command, "openvpn-openssl"):
            opkg.update(ssh_command)
            opkg.install(ssh_command, "openvpn-openssl")
            sync(ssh_command)

    def step_openwrt_setup_openvpn() -> None:
        mkdir(ssh_command, "/etc/openvpn")
        put_file(ssh_command, Path("/etc") / "openvpn" / "ca.crt", pki.ca_cert)
        put_file(ssh_command, Path("/etc") / "openvpn" / "client.crt", pki.client_cert)
        put_file(ssh_command, Path("/etc") / "openvpn" / "client.key", pki.client_key)
        uci.set(ssh_command, "openvpn.sample_client.enabled", True)
        uci.set(ssh_command, "openvpn.sample_client.remote", f"{openvpn_server_name} {openvpn_server_port}")
        uci.commit(ssh_command, "openvpn")
        service.restart(ssh_command, "openvpn", "sample_client")

    def step_openwrt_configure_firewall() -> None:
        uci.add_list(ssh_command, "firewall.@zone[0].device", "tun0")
        uci.commit(ssh_command, "firewall")
        service.restart(ssh_command, "firewall")

    def step_verify_connected() -> None:
        assert run(ssh_command, "ping -c 5 192.168.123.1")
        tun0_ips = openwrt.get_ip_addr(ssh_command, "tun0")
        assert len(tun0_ips) == 1
        assert openvpn_server_env.exec("openvpn-server", f"ping -c 5 {tun0_ips[0]}")

    step_openwrt_install_openvpn()
    step_openwrt_setup_openvpn()
    step_openwrt_configure_firewall()
    step_verify_connected()
