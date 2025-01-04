import time

from labgrid.driver import ShellDriver, SSHDriver
from process import run


def restart(shell: ShellDriver | SSHDriver, name: str, wait: float | None = None) -> None:
    run(shell, f"service {name} restart")
    if wait:
        time.sleep(wait)
