import time

from labgrid.driver import ShellDriver, SSHDriver
from process import run


def restart(shell: ShellDriver | SSHDriver, name: str, unit: str | None = None, wait: float | None = None) -> None:
    run(shell, f"service {name} restart" if unit is None else f"service {name} restart {unit}")
    if wait:
        time.sleep(wait)
