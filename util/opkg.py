from dataclasses import dataclass

from labgrid.driver import ShellDriver, SSHDriver
from process import run


@dataclass
class Package:
    name: str
    version: str


def list_installed(shell: ShellDriver | SSHDriver) -> list[Package]:
    """Parses the output of `opkg list-installed` and returns a list of Package objects."""
    return [Package(*line.split(" - ", 1)) for line in run(shell, "opkg list-installed").splitlines() if " - " in line]


def list_installed_names(shell: ShellDriver | SSHDriver) -> list[str]:
    # return [line.partition(" ")[0] for line in run(shell, "opkg list-installed").splitlines() if line]
    return [package.name for package in list_installed(shell)]


def is_package_installed(shell: ShellDriver | SSHDriver, package: str) -> bool:
    return package in list_installed_names(shell)


def update(shell: ShellDriver | SSHDriver) -> None:
    run(shell, "opkg update")


def install(shell: ShellDriver | SSHDriver, package: str) -> None:
    run(shell, f"opkg install {package}")
