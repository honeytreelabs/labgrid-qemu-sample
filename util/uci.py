from labgrid.driver import ShellDriver, SSHDriver
from process import run


def _to_uci_value(value: str | int | bool) -> str:
    if value is True:
        return "1"
    elif value is False:
        return "0"
    return str(value)


def set(shell: ShellDriver | SSHDriver, key: str, value: str | int | bool) -> None:
    run(shell, f'uci set {key}="{_to_uci_value(value)}"')


def get(shell: ShellDriver | SSHDriver, key: str) -> str:
    return run(shell, f"uci get {key}")


def add_list(shell: ShellDriver | SSHDriver, key: str, value: str | int | bool) -> None:
    run(shell, f'uci add_list {key}="{_to_uci_value(value)}"')


def commit(shell: ShellDriver | SSHDriver, section: str | None = None) -> None:
    if section:
        run(shell, f"uci commit {section}")
        return
    run(shell, "uci commit")
