import select
import socket
import time
from dataclasses import dataclass

import attr
from labgrid.driver import Driver
from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
from labgrid.protocol import ConsoleProtocol
from labgrid.step import step
from pexpect import TIMEOUT
from qmp import QMPMonitor


@dataclass(frozen=True)
class Endpoint:
    addr: str
    port: int


@dataclass
class PortForwarding:
    local: Endpoint
    remote: Endpoint


@attr.s(eq=False)
class BaseQEMUDriver(ConsoleExpectMixin, Driver, ConsoleProtocol):
    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        self.txdelay = None
        self._socket: socket.socket | None = None
        self._forwarded_ports: dict[Endpoint, Endpoint] = {}

    def on_activate(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect(("localhost", 12345))

    def on_deactivate(self) -> None:
        assert self._socket

        self._socket.close()
        self._socket = None

    @step(result=True, args=["command", "arguments"])
    def monitor_command(self, command: str, arguments: dict | None = None) -> str:
        """Execute a monitor_command via the QMP"""
        socket_qmp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_qmp.connect(("localhost", 4444))
        try:
            qmp_file = socket_qmp.makefile("rw")

            def write_flush(msg: str) -> None:
                qmp_file.write(msg)
                qmp_file.flush()

            qmp = QMPMonitor(qmp_file.readline, write_flush)

            if arguments is None:
                arguments = {}
            return qmp.execute(command, arguments)
        finally:
            socket_qmp.close()

    def _add_port_forward(self, local_address: str, local_port: int, remote_address: str, remote_port: int) -> None:
        proto: str = "tcp"  # only this protocol is currently supported
        self.monitor_command(
            "human-monitor-command",
            {"command-line": f"hostfwd_add {proto}:{local_address}:{local_port}-{remote_address}:{remote_port}"},
        )

    def add_port_forward(
        self, local_address: str, local_port: int, remote_address: str, remote_port: int
    ) -> PortForwarding:
        local_endpoint = Endpoint(local_address, local_port)
        if local_endpoint in self._forwarded_ports:
            return PortForwarding(local_endpoint, self._forwarded_ports[local_endpoint])
        self._add_port_forward(local_address, local_port, remote_address, remote_port)
        remote_endpoint = Endpoint(
            remote_address,
            remote_port,
        )
        self._forwarded_ports[local_endpoint] = remote_endpoint
        return PortForwarding(local_endpoint, remote_endpoint)

    def remove_port_forward(self, local_endpoint: Endpoint) -> None:
        proto: str = "str"  # only this protocol is currently supported
        del self._forwarded_ports[local_endpoint]
        self.monitor_command(
            "human-monitor-command",
            {"command-line": f"hostfwd_remove {proto}:{local_endpoint.addr}:{local_endpoint.port}"},
        )

    def _read(self, size: int = 1, timeout: float = 10, max_size: int | None = None) -> bytes:
        assert self._socket

        ready, _, _ = select.select([self._socket], [], [], timeout)
        if ready:
            # Collect some more data
            time.sleep(0.01)
            # Always read a page, regardless of size
            size = 4096
            size = min(max_size, size) if max_size else size
            res = self._socket.recv(size)
        else:
            raise TIMEOUT(f"Timeout of {timeout:.2f} seconds exceeded")
        return res

    def _write(self, data: bytes) -> int:  # type: ignore
        assert self._socket

        return self._socket.send(data)

    def __str__(self) -> str:
        assert self.target
        return f"QemuDriver({self.target.name})"
