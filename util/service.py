import time
from typing import Optional

from labgrid.driver import ShellDriver, SSHDriver

from process import run


def restart(shell: ShellDriver | SSHDriver, name: str, wait: Optional[float] = None) -> None:
    run(shell, f"/etc/init.d/{name} restart")
    if wait:
        time.sleep(wait)
