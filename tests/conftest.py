from ipaddress import IPv4Address

import pytest
from labgrid import Target
from labgrid.driver import ShellDriver, SSHDriver
from openwrt import get_default_interface_device_name, get_ip_addr
from strategy import QEMUBaseStrategy, Status


@pytest.fixture(scope="module")
def shell_command(target: Target, strategy: QEMUBaseStrategy) -> ShellDriver:
    if strategy.status != Status.shell and strategy.status != Status.ssh:
        strategy.transition("shell")
    return target.get_driver("ShellDriver")


@pytest.fixture(scope="module")
def dhcp_ip(shell_command: ShellDriver, strategy: QEMUBaseStrategy) -> list[IPv4Address]:
    strategy.transition("internet")
    return get_ip_addr(shell_command, get_default_interface_device_name(shell_command))


@pytest.fixture(scope="module")
def ssh_command(target: Target, strategy: QEMUBaseStrategy) -> SSHDriver:
    strategy.transition("ssh")
    return target.get_driver("SSHDriver")
