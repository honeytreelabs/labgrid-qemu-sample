from func import wait_for
from labgrid.driver import ShellDriver, SSHDriver


def wait_for_shell_cmd(
    shell: ShellDriver | SSHDriver,
    command: str,
    delay: float = 0.1,
    timeout: float = 10,
) -> None:
    """Wait for a shell command to complete successfully.

    :param shell: The shell to interact with.
    :param command: The command to evaluate in given shell.
    :param delay: Time in seconds to wait between condition checks.
    :param timeout: Timeout in seconds to wait for the condition to become true.
    :raises TimeoutError: If the condition does not become true within the timeout.
    """

    wait_for(
        lambda: shell.run(command)[2] == 0,
        f"Waiting for command '{command}'",
        delay=delay,
        timeout=timeout,
    )
