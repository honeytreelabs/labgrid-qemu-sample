from process import shell_run
from strategy.qemu_strategy import QEMUBaseStrategy


def test_ssh_version(strategy: QEMUBaseStrategy) -> None:
    strategy.transition("ssh")
    assert strategy.ssh_port_forwarding is not None, "Port-Forwarding must be active"
    ssh_output = shell_run(
        f"ssh -vv -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {strategy.ssh_port_forwarding.local.port} root@{strategy.ssh_port_forwarding.local.addr} /bin/true"
    )
    assert "Remote protocol version 2.0" in ssh_output, "Remote SSH protocol version must be 2.0"
    assert "remote software version dropbear" in ssh_output, "Remote SSH server must be dropbear"
