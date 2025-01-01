import attr
import service
import uci
from driver import StatefulQEMUDriver
from func import retry_exc
from labgrid import step, target_factory
from labgrid.driver import ShellDriver, SSHDriver
from labgrid.driver.exception import ExecutionError
from labgrid.step import Step
from labgrid.strategy import Strategy, StrategyError
from labgrid.util import get_free_port

from .status import Status


@target_factory.reg_driver
@attr.s(eq=False)
class QEMUStatefulStrategy(Strategy):
    bindings = {
        "qemu": "StatefulQEMUDriver",
        "shell": "ShellDriver",
        "ssh": "SSHDriver",
    }

    status: Status = attr.ib(default=Status.unknown)
    qemu: StatefulQEMUDriver | None = None
    shell: ShellDriver | None = None
    ssh: SSHDriver | None = None

    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        self.__port_forward = None
        self.__remote_port = self.ssh.networkservice.port

    @step(result=True)
    def get_remote_address(self) -> str:
        return str(self.shell.get_ip_addresses()[0].ip)

    def update_network_service(self) -> None:
        assert self.target
        assert self.qemu

        new_address: str = retry_exc(self.get_remote_address, ExecutionError, "getting the remote address", timeout=20)
        networkservice = self.ssh.networkservice  # type: ignore

        if networkservice.address != new_address:
            self.target.deactivate(self.ssh)

            if self.__port_forward is not None:
                self.qemu.remove_port_forward(*self.__port_forward)

            local_port = get_free_port()
            local_address = "127.0.0.1"

            self.qemu.add_port_forward(
                "tcp",
                local_address,
                local_port,
                new_address,
                self.__remote_port,
            )
            self.__port_forward = ("tcp", local_address, local_port)

            networkservice.address = local_address
            networkservice.port = local_port

    @step(args=["state"])
    def transition(self, state: Status | str, *, step: Step) -> None:
        if not isinstance(state, Status):
            state = Status[state]

        if state == Status.unknown:
            raise StrategyError(f"can not transition to {state}")

        elif self.status == state:
            step.skip("nothing to do")
            return

        elif state == Status.shell:
            assert self.target
            assert self.qemu

            # check if target is running
            self.target.activate(self.qemu)
            self.target.activate(self.shell)

            assert self.shell
            if uci.get(self.shell, "network.lan.proto") != "dhcp":
                uci.set(self.shell, "network.lan.proto", "dhcp")
                uci.commit(self.shell, "network")
                service.restart(self.shell, "network", wait=1)

        elif state == Status.ssh:
            self.transition(Status.shell)

            assert self.shell
            self.update_network_service()
        else:
            raise StrategyError(f"no transition found from {self.status} to {status}")

        self.status = state
