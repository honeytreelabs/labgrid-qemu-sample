from typing import Optional

from labgrid.driver import ShellDriver, SSHDriver
from process import run


def set(shell: ShellDriver | SSHDriver, key: str, value: str) -> None:
    run(shell, f'uci set {key}="{value}"')


def get(shell: ShellDriver | SSHDriver, key: str) -> str:
    return run(shell, f"uci get {key}")


def commit(shell: ShellDriver | SSHDriver, section: Optional[str] = None) -> None:
    if section:
        run(shell, f"uci commit {section}")
        return
    run(shell, "uci commit")
