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
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed_process.stdout


def run(shell: Runner, cmd: str) -> str:
    return "\n".join(shell.run_check(cmd))


def kill_process(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate(timeout=1)
