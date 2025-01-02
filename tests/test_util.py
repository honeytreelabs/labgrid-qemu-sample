import json
from dataclasses import dataclass
from ipaddress import IPv4Address
from unittest.mock import MagicMock, patch

import network
import openwrt
import pytest


@dataclass
class IPTest:
    ip_output: str
    ip_addresses: list[IPv4Address]


@pytest.mark.parametrize(
    "ip_test",
    [
        IPTest(
            "5: tun0    inet 172.17.0.6 peer 172.17.0.5/32 scope global tun0\\       valid_lft forever preferred_lft forever",
            [IPv4Address("172.17.0.6")],
        ),
        IPTest(
            """3: br-lan    inet 192.168.187.100/24 brd 192.168.187.255 scope global br-lan\\       valid_lft forever preferred_lft forever
3: br-lan    inet 192.168.45.45/24 scope global br-lan\\       valid_lft forever preferred_lft forever
""",
            [IPv4Address("192.168.187.100"), IPv4Address("192.168.45.45")],
        ),
    ],
)
def test_openwrt_get_ip_addr_ok(ip_test: IPTest) -> None:
    runner = MagicMock()
    runner.run_check.side_effect = [ip_test.ip_output.split("\n")]
    assert openwrt.get_ip_addr(runner, "tun0") == ip_test.ip_addresses


@pytest.mark.parametrize(
    "ip_test",
    [
        IPTest(
            """default via 192.168.187.2 dev br-lan  src 192.168.187.100 
192.168.187.0/24 dev br-lan scope link  src 192.168.187.100
""",
            [IPv4Address("192.168.187.2")],
        ),
    ],
)
def test_openwrt_get_gateway_ip_ok(ip_test: IPTest) -> None:
    runner = MagicMock()
    runner.run_check.side_effect = [ip_test.ip_output.split("\n")]
    assert openwrt.get_gateway_ip(runner) == ip_test.ip_addresses


@patch("network.shell_run")
def test_primary_host_ip_ok(mock_shell_run: MagicMock) -> None:
    ip_r_s_output = json.dumps([{"dev": "eth0"}])
    ip_a_s_output = json.dumps([{"addr_info": [{"local": "192.168.1.1"}]}])
    mock_shell_run.side_effect = [ip_r_s_output, ip_a_s_output]

    assert network.primary_host_ip() == IPv4Address("192.168.1.1")
