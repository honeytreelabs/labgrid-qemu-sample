from labgrid.driver import ShellDriver, SSHDriver


def run(shell: ShellDriver | SSHDriver, cmd: str) -> str:
    return "\n".join(shell.run_check(cmd))
