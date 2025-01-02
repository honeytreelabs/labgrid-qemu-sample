from ipaddress import IPv4Address

import pytest
from labgrid import Target
from labgrid.driver import ShellDriver, SSHDriver
from openwrt import enable_dhcp
from strategy import QEMUNetworkStrategy, Status


@pytest.fixture(scope="module")
def shell_command(target: Target, strategy: QEMUNetworkStrategy) -> ShellDriver:
    if strategy.status != Status.shell and strategy.status != Status.ssh:
        strategy.transition("shell")
    return target.get_driver("ShellDriver")


@pytest.fixture(scope="module")
def ssh_command(target: Target, strategy: QEMUNetworkStrategy) -> SSHDriver:
    strategy.transition("ssh")
    return target.get_driver("SSHDriver")


@pytest.fixture(scope="module")
def dhcp_ip(shell_command: ShellDriver) -> list[IPv4Address]:
    return enable_dhcp(shell_command)
