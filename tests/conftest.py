from collections.abc import Iterator
from ipaddress import IPv4Address

import pytest
from docker import ComposeEnv, ComposeEnvFactory
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


@pytest.fixture(scope="module")
def compose_env_factory() -> Iterator[ComposeEnvFactory]:
    compose_envs: list[ComposeEnv] = []

    def _compose_env_factory(compose_yaml: str, data: dict[str, bytes]) -> ComposeEnv:
        compose_env = ComposeEnv(compose_yaml, data)
        compose_envs.append(compose_env)
        compose_env.up(build=True)
        return compose_env

    yield _compose_env_factory

    for compose_env in compose_envs:
        compose_env.rm(force=True, stop=True)
        compose_env.kill()
        compose_env.cleanup()
