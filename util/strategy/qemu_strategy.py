from abc import ABC, abstractmethod

import attr
from driver import BaseQEMUDriver, QEMUParams
from func import retry_exc
from labgrid import step
from labgrid.driver import ShellDriver, SSHDriver
from labgrid.driver.exception import ExecutionError
from labgrid.step import Step
from labgrid.strategy import Strategy, StrategyError
from labgrid.util import get_free_port
from openwrt import enable_dhcp, enable_local_dns_queries

from .status import Status


class QEMUBaseStrategy(ABC, Strategy):
    status: Status = attr.ib(default=Status.unknown)
    qemu: BaseQEMUDriver | None = None
    shell: ShellDriver | None = None
    ssh: SSHDriver | None = None
    params: QEMUParams | None = None

    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        self._port_forward: tuple[str, str, int] | None = None
        self._remote_port: int = self.ssh.networkservice.port

    @abstractmethod
    def on(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def off(self) -> None:
        raise NotImplementedError()

    @step(result=True)
    def get_remote_address(self) -> str:
        assert self.shell

        return str(self.shell.get_ip_addresses()[0].ip)

    @step()
    def update_network_service(self) -> None:
        assert self.target
        assert self.qemu
        assert self.ssh
        assert self._remote_port

        new_address: str = retry_exc(self.get_remote_address, ExecutionError, "getting the remote address", timeout=20)
        networkservice = self.ssh.networkservice

        if networkservice.address != new_address:
            self.target.deactivate(self.ssh)

            if self._port_forward is not None:
                self.qemu.remove_port_forward(*self._port_forward)

            local_port = get_free_port()
            local_address = "127.0.0.1"

            self.qemu.add_port_forward(
                "tcp",
                local_address,
                local_port,
                new_address,
                self._remote_port,
            )
            self._port_forward = ("tcp", local_address, local_port)

            networkservice.address = local_address
            networkservice.port = local_port

    @step(args=["status"])
    def transition(self, status: Status | str, *, step: Step | None = None) -> None:  # type: ignore
        assert step

        if not isinstance(status, Status):
            status = Status[status]

        if status == Status.unknown:
            raise StrategyError(f"can not transition to {status}")  # type: ignore

        elif self.status == status:
            step.skip("nothing to do")
            return

        if status == Status.off:
            assert self.target
            assert self.qemu

            self.target.deactivate(self.qemu)
            self.off()

        elif status == Status.shell:
            assert self.target
            assert self.qemu

            self.on()
            self.target.activate(self.qemu)
            self.target.activate(self.shell)

            assert self.shell

        elif status == Status.internet:
            self.transition(Status.shell)

            assert self.shell
            enable_dhcp(self.shell)
            enable_local_dns_queries(self.shell)

        elif status == Status.ssh:
            self.transition(Status.internet)

            assert self.shell
            self.update_network_service()

        self.status = status
