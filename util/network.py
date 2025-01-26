import json
import socket
from contextlib import closing
from ipaddress import IPv4Address
from socket import AF_INET, SOCK_DGRAM, SOCK_STREAM

from process import shell_run


def primary_host_ip() -> IPv4Address:
    ip_r_s_str = shell_run("ip -4 -json r s")
    ip_r_s = json.loads(ip_r_s_str)
    primary_interface = ip_r_s[0]["dev"]
    ip_a_s_str = shell_run(f"ip -4 -json -o addr show dev {primary_interface}")
    ip_a_s = json.loads(ip_a_s_str)
    return IPv4Address(ip_a_s[0]["addr_info"][0]["local"])


class NetworkError(Exception):
    pass


def resolve(name: str) -> IPv4Address:
    try:
        return IPv4Address(socket.gethostbyname(name))
    except socket.gaierror as exc:
        raise NetworkError from exc


def is_port_in_use(port: int, kind: socket.SocketKind = socket.SOCK_STREAM) -> bool:
    with socket.socket(socket.AF_INET, kind) as s:
        return s.connect_ex(("localhost", port)) == 0


def get_free_tcp_port() -> int:
    with closing(socket.socket(AF_INET, SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def get_free_udp_port() -> int:
    with closing(socket.socket(AF_INET, SOCK_DGRAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def is_tcp_endpoint_reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    """
    Check if a connection to a given host and port is successful.

    :param host: The hostname or IP address of the server.
    :param port: The port number to connect to.
    :param timeout: The number of seconds to wait before timing out.
    :return: True if the connection is successful, False otherwise.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (TimeoutError, OSError):
        return False
