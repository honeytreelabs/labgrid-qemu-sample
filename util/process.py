import subprocess

from labgrid.driver import ShellDriver, SSHDriver

Runner = ShellDriver | SSHDriver


def shell_run(cmd: str, shell: str = "/bin/bash") -> str:
    # we explicitly want to run code in a bash shell
    completed_process = subprocess.run(  # noqa: S602
        cmd,
        check=True,
        shell=True,
        executable=shell,
        capture_output=True,
        text=True,
    )
    return completed_process.stdout


def run(shell: Runner, cmd: str) -> str:
    return "\n".join(shell.run_check(cmd))
