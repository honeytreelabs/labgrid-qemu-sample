from ipaddress import IPv4Address
from unittest.mock import MagicMock

import openwrt


def test_openwrt_get_ip_addr_ok() -> None:
    runner = MagicMock()
    runner.run_check.side_effect = [
        [
            "5: tun0    inet 172.17.0.6 peer 172.17.0.5/32 scope global tun0\\       valid_lft forever preferred_lft forever"
        ]
    ]
    assert openwrt.get_ip_addr(runner, "tun0") == IPv4Address("172.17.0.6")
