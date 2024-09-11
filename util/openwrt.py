import re
from ipaddress import IPv4Address

from process import Runner, run

IPV4_ADDR_REGEX = re.compile(r"\s+(\d+\.\d+\.\d+\.\d+)\s+")


def get_ip_addr(runner: Runner, if_name: str) -> IPv4Address:
    ip_output = run(runner, f"ip -4 -o addr show dev {if_name}")
    match = IPV4_ADDR_REGEX.search(ip_output)
    if not match:
        raise ValueError("No IPv4 address could be found.")
    return IPv4Address(match.group(1))
