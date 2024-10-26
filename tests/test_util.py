import json
from ipaddress import IPv4Address
from unittest.mock import MagicMock, patch

import network
import openwrt


def test_openwrt_get_ip_addr_ok() -> None:
    runner = MagicMock()
    runner.run_check.side_effect = [
        [
            "5: tun0    inet 172.17.0.6 peer 172.17.0.5/32 scope global tun0\\       valid_lft forever preferred_lft forever"
        ]
    ]
    assert openwrt.get_ip_addr(runner, "tun0") == IPv4Address("172.17.0.6")


@patch("network.shell_run")
def test_primary_host_ip_ok(mock_shell_run: MagicMock) -> None:
    ip_r_s_output = json.dumps([{"dev": "eth0"}])
    ip_a_s_output = json.dumps([{"addr_info": [{"local": "192.168.1.1"}]}])
    mock_shell_run.side_effect = [ip_r_s_output, ip_a_s_output]

    assert network.primary_host_ip() == IPv4Address("192.168.1.1")
