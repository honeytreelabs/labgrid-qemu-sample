import subprocess

from labgrid.driver import ShellDriver, SSHDriver

Runner = ShellDriver | SSHDriver


def bash_run(cmd: str) -> str:
    completed_process = subprocess.run(
        cmd,
        check=True,
        shell=True,
        executable="/bin/bash",
        capture_output=True,
        text=True,
    )
    return completed_process.stdout


def run(shell: Runner, cmd: str) -> str:
    return "\n".join(shell.run_check(cmd))
