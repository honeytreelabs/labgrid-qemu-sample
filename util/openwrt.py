import re
from functools import partial
from ipaddress import IPv4Address

import service
import uci
from func import wait_for
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


IPV4_PRIMARY_IF_NAME_REGEX = re.compile(r"default\s+via\s+\d+\.\d+\.\d+\.\d+\s+dev\s+([a-z-]+)")


def get_default_interface_device_name(runner: Runner) -> str:
    ip_output = run(runner, "ip -4 r s default")
    matches = IPV4_PRIMARY_IF_NAME_REGEX.findall(ip_output)
    return matches[0]


def enable_dhcp(runner: Runner) -> list[IPv4Address]:
    if uci.get(runner, "network.lan.proto") != "dhcp":
        uci.set(runner, "network.lan.proto", "dhcp")
        uci.commit(runner, "network")
        service.restart(runner, "network", wait=1)
    assert wait_for(partial(get_gateway_ip, runner), "gateway IP has been assigned", delay=1)
    return get_ip_addr(runner, get_default_interface_device_name(runner))
