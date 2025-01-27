import re
import select
import socket
import time
from dataclasses import dataclass

import attr
from labgrid.driver import Driver
from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
from labgrid.protocol import ConsoleProtocol
from labgrid.step import step
from labgrid.util import get_free_port
from pexpect import TIMEOUT
from qmp import QMPMonitor

from driver.params import get_qmp_port


@dataclass(frozen=True)
class Endpoint:
    addr: str
    port: int


PORT_FORWARDING_PATTERN = re.compile(r"TCP\[HOST_FORWARD\]\s+\d+\s+([\w\.-]+)\s+(\d+)\s+([\w\.-]+)\s+(\d+)")


def parse_port_forwardings(qmp_output: str) -> dict[Endpoint, Endpoint]:
    result: dict[Endpoint, Endpoint] = {}
    for match in PORT_FORWARDING_PATTERN.findall(qmp_output):
        src_address, src_port, dst_address, dst_port = match
        result[Endpoint(dst_address, int(dst_port))] = Endpoint(src_address, int(src_port))
    return result


@attr.s(eq=False)
class BaseQEMUDriver(ConsoleExpectMixin, Driver, ConsoleProtocol):
    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        self.txdelay = None
        self._socket: socket.socket | None = None

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
        socket_qmp.connect(("localhost", get_qmp_port()))
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

    def add_hostfwd(self, remote_address: str, remote_port: int) -> Endpoint:
        remote_endpoint = Endpoint(remote_address, remote_port)
        host_forward = self.port_forwardings  # cache
        if remote_endpoint in host_forward:
            return host_forward[remote_endpoint]
        local_endpoint = Endpoint("127.0.0.1", get_free_port())
        self._add_port_forward(local_endpoint.addr, local_endpoint.port, remote_address, remote_port)
        return local_endpoint

    def add_port_forwarding(self, local_address: str, local_port: int, remote_address: str, remote_port: int) -> None:
        local_endpoint = Endpoint(local_address, local_port)
        remote_endpoint = Endpoint(remote_address, remote_port)
        host_forward = self.port_forwardings  # cache
        if host_forward.get(remote_endpoint, None) == local_endpoint:
            return
        self.remove_port_forward(remote_endpoint)
        self._add_port_forward(local_endpoint.addr, local_endpoint.port, remote_address, remote_port)

    def remove_port_forward(self, local_endpoint: Endpoint) -> None:
        proto: str = "str"  # only this protocol is currently supported
        self.monitor_command(
            "human-monitor-command",
            {"command-line": f"hostfwd_remove {proto}:{local_endpoint.addr}:{local_endpoint.port}"},
        )

    @property
    def port_forwardings(self) -> dict[Endpoint, Endpoint]:
        qmp_output = self.monitor_command("human-monitor-command", {"command-line": "info usernet"})
        return parse_port_forwardings(qmp_output)

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
