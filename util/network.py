import json
import socket
from ipaddress import IPv4Address

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
