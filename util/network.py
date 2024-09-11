import json
from ipaddress import IPv4Address

from process import bash_run


def primary_host_ip() -> IPv4Address:
    ip_cfg_str = bash_run("ip -4 -json r s")
    ip_cfg = json.loads(ip_cfg_str)
    primary_ip = ip_cfg[0]["prefsrc"]
    return IPv4Address(primary_ip)
