import re
from ipaddress import IPv4Address

from process import Runner, run

IPV4_ADDR_REGEX = re.compile(r"inet\s+(\d+\.\d+\.\d+\.\d+)")


def get_ip_addr(runner: Runner, if_name: str) -> list[IPv4Address]:
    ip_output = run(runner, f"ip -4 -o addr show dev {if_name}")
    matches = IPV4_ADDR_REGEX.findall(ip_output)
    return [IPv4Address(match) for match in matches]


IPV4_GATEWAY_IP_REGEX = re.compile(r"default\s+via\s+(\d+\.\d+\.\d+\.\d+)")


def get_gateway_ip(runner: Runner) -> list[IPv4Address]:
    ip_output = run(runner, "ip -4 r s default")
    matches = IPV4_GATEWAY_IP_REGEX.findall(ip_output)
    return [IPv4Address(match) for match in matches]
