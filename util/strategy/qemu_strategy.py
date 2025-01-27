from abc import ABC, abstractmethod
from functools import partial

import attr
from driver import BaseQEMUDriver, QEMUParams
from driver.base_qemudriver import Endpoint
from func import retry_exc, wait_for
from labgrid import step
from labgrid.driver import ShellDriver, SSHDriver
from labgrid.driver.exception import ExecutionError
from labgrid.step import Step
from labgrid.strategy import Strategy, StrategyError
from network import is_tcp_endpoint_reachable
from openwrt import enable_dhcp, enable_local_dns_queries

from .status import Status


class SetupError(Exception):
    pass


class QEMUBaseStrategy(ABC, Strategy):
    status: Status = attr.ib(default=Status.unknown)
    qemu: BaseQEMUDriver | None = None
    shell: ShellDriver | None = None
    ssh: SSHDriver | None = None
    params: QEMUParams | None = None

    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        self._ssh_local_endpoint: Endpoint | None = None
        self._ssh_remote_port: int = self.ssh.networkservice.port

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

    @property
    def local_ssh_endpoint(self) -> Endpoint | None:
        return self._ssh_local_endpoint

    @step()
    def update_network_service(self) -> None:
        assert self.target
        assert self.qemu
        assert self.ssh
        assert self._ssh_remote_port

        dst_address: str = retry_exc(self.get_remote_address, ExecutionError, "getting the remote address", timeout=20)
        networkservice = self.ssh.networkservice

        if networkservice.address != dst_address:
            self.target.deactivate(self.ssh)

            if self._ssh_local_endpoint is not None:
                self.qemu.remove_port_forward(self._ssh_local_endpoint)

            self._ssh_local_endpoint = self.qemu.add_hostfwd(
                dst_address,
                self._ssh_remote_port,
            )

            networkservice.address = self._ssh_local_endpoint.addr
            networkservice.port = self._ssh_local_endpoint.port

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
            if self.local_ssh_endpoint is None:
                raise SetupError("SSH portforwarding could not be established")
            connected = wait_for(
                partial(is_tcp_endpoint_reachable, self.local_ssh_endpoint.addr, self.local_ssh_endpoint.port),
                "SSH connection can be established",
            )
            if not connected:
                raise SetupError("Could not connect to SSH port of DUT.")

        self.status = status
