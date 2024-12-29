"""The QEMUDriver implements a driver to use a QEMU target"""

import atexit
import re
import select
import shlex
import socket
import subprocess
import time
from typing import Callable

import attr
from labgrid.driver import Driver
from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
from labgrid.driver.exception import ExecutionError
from labgrid.factory import target_factory
from labgrid.protocol import ConsoleProtocol, PowerProtocol
from labgrid.step import step
from labgrid.util.qmp import QMPError, QMPMonitor
from pexpect import TIMEOUT


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def wait_for(cond: Callable[[], bool], desc: str, timeout: int = 10) -> None:
    """
    Wait for a Unix domain socket to appear at the specified path.

    :param cond: Condition to wait to become true
    :param desc: Description of what to wait for
    :param timeout: Timeout in seconds to wait for the socket.
    :raises TimeoutError: If the socket does not appear within the timeout.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if cond():
            return
        time.sleep(0.1)  # Sleep briefly to avoid busy-waiting
    raise TimeoutError(f"Timeout while waiting for condition to become true: {desc}.")


def kill_process(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate(timeout=1)


def start_ser2net_mux(port_conn: int, port_accept: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            "ser2net",
            "-n",
            "-d",
            "-Y",
            "connection: &con01",
            "-Y",
            f"  connector: telnet(rfc2217), tcp,{port_conn}",
            "-Y",
            f"  accepter: telnet(rfc2217,mode=server),tcp,{port_accept}",
            "-Y",
            "  options:",
            "-Y",
            "    max-connections: 10",
            "-Y",
            "    mdns: false",
        ],
    )


@target_factory.reg_driver
@attr.s(eq=False)
class CustomQEMUDriver(ConsoleExpectMixin, Driver, PowerProtocol, ConsoleProtocol):
    """
    The QEMUDriver implements an interface to start targets as qemu instances.

    The kernel, flash, rootfs and dtb arguments refer to images and paths
    declared in the environment configuration.

    Args:
        qemu_bin (str): reference to the tools key for the QEMU binary
        machine (str): QEMU machine type
        cpu (str): QEMU cpu type
        memory (str): QEMU memory size (ends with M or G)
        extra_args (str): extra QEMU arguments, they are passed directly to the QEMU binary
        boot_args (str): optional, additional kernel boot argument
        kernel (str): optional, reference to the images key for the kernel
        disk (str): optional, reference to the images key for the disk image
        disk_opts (str): optional, additional QEMU disk options
        flash (str): optional, reference to the images key for the flash image
        rootfs (str): optional, reference to the paths key for use as the virtio-9p filesystem
        dtb (str): optional, reference to the image key for the device tree
        bios (str): optional, reference to the image key for the bios image
        display (str, default="none"): optional, display output to enable; must be one of:
            none: Do not create a display device
            fb-headless: Create a headless framebuffer device
            egl-headless: Create a headless GPU-backed graphics card. Requires host support
        nic (str): optional, configuration string to pass to QEMU to create a network interface
    """

    qemu_bin: str | None = attr.ib(default=None, validator=attr.validators.instance_of(str))
    machine: str | None = attr.ib(default=None, validator=attr.validators.instance_of(str))
    cpu: str | None = attr.ib(default=None, validator=attr.validators.instance_of(str))
    memory: str | None = attr.ib(default=None, validator=attr.validators.instance_of(str))
    extra_args: str | None = attr.ib(default=None, validator=attr.validators.instance_of(str))
    boot_args: str | None = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    kernel: str | None = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    disk: str | None = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    disk_opts: str | None = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    rootfs: str | None = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    dtb: str | None = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    flash: str | None = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    bios: str | None = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    display: str | None = attr.ib(
        default="none",
        validator=attr.validators.optional(
            attr.validators.and_(
                attr.validators.instance_of(str),
                attr.validators.in_(["none", "fb-headless", "egl-headless"]),
            )
        ),
    )
    nic: str | None = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    ser2net: bool = attr.ib(default=False, validator=attr.validators.instance_of(bool))

    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        self.status = 0
        self.txdelay = None
        self._child_qemu: subprocess.Popen | None = None
        self._child_ser2net: subprocess.Popen | None = None
        self._socket = None
        self._forwarded_ports = {}
        atexit.register(self._atexit)

    def _atexit(self) -> None:
        kill_process(self._child_qemu)
        self._child_qemu = None
        kill_process(self._child_ser2net)
        self._child_ser2net = None

    def get_qemu_version(self, qemu_bin: str) -> tuple[int, int, int]:
        p = subprocess.run([qemu_bin, "-version"], stdout=subprocess.PIPE, encoding="utf-8")
        if p.returncode != 0:
            raise ExecutionError(f"Unable to get QEMU version. QEMU exited with: {p.returncode}")  # type: ignore

        m = re.search(r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<micro>\d+)", p.stdout.splitlines()[0])
        if m is None:
            raise ExecutionError(f"Unable to find QEMU version in: {p.stdout.splitlines()[0]}")  # type: ignore

        return (int(m.group("major")), int(m.group("minor")), int(m.group("micro")))

    def get_qemu_base_args(self) -> list[str]:
        """Returns the base command line used for Qemu without the options
        related to QMP. These options can be used to start an interactive
        Qemu manually for debugging tests
        """
        assert self.target
        assert self.extra_args
        assert self.machine
        assert self.cpu
        assert self.memory

        cmd: list[str] = []

        qemu_bin = self.target.env.config.get_tool(self.qemu_bin)
        if qemu_bin is None:
            raise KeyError("QEMU Binary Path not configured in tools configuration key")
        cmd = [qemu_bin]

        qemu_version = self.get_qemu_version(qemu_bin)

        boot_args = []

        if self.kernel is not None:
            cmd.append("-kernel")
            cmd.append(self.target.env.config.get_image_path(self.kernel))
        if self.disk is not None:
            disk_path = self.target.env.config.get_image_path(self.disk)
            disk_format = "raw"
            if disk_path.endswith(".qcow2"):
                disk_format = "qcow2"
            disk_opts = ""
            if self.disk_opts:
                disk_opts = f",{self.disk_opts}"
            if self.machine == "vexpress-a9":
                cmd.append("-drive")
                cmd.append(f"if=sd,format={disk_format},file={disk_path},id=mmc0{disk_opts}")
                boot_args.append("root=/dev/mmcblk0p1 rootfstype=ext4 rootwait")
            elif self.machine in ["pc", "q35", "virt"]:
                cmd.append("-drive")
                cmd.append(f"if=virtio,format={disk_format},file={disk_path}{disk_opts}")
                boot_args.append("root=/dev/vda rootwait")
            else:
                raise NotImplementedError(f"QEMU disk image support not implemented for machine '{self.machine}'")
        if self.rootfs is not None:
            cmd.append("-fsdev")
            cmd.append(f"local,id=rootfs,security_model=none,path={self.target.env.config.get_path(self.rootfs)}")  # pylint: disable=line-too-long
            cmd.append("-device")
            cmd.append("virtio-9p-device,fsdev=rootfs,mount_tag=/dev/root")
            boot_args.append("root=/dev/root rootfstype=9p rootflags=trans=virtio")
        if self.dtb is not None:
            cmd.append("-dtb")
            cmd.append(self.target.env.config.get_image_path(self.dtb))
        if self.flash is not None:
            cmd.append("-drive")
            cmd.append(f"if=pflash,format=raw,file={self.target.env.config.get_image_path(self.flash)},id=nor0")  # pylint: disable=line-too-long
        if self.bios is not None:
            cmd.append("-bios")
            cmd.append(self.target.env.config.get_image_path(self.bios))

        if "-append" in shlex.split(self.extra_args):
            raise ExecutionError("-append in extra_args not allowed, use boot_args instead")  # type: ignore

        cmd.extend(shlex.split(self.extra_args))
        cmd.append("-machine")
        cmd.append(self.machine)
        cmd.append("-cpu")
        cmd.append(self.cpu)
        cmd.append("-m")
        cmd.append(self.memory)
        if self.display == "none":
            cmd.append("-nographic")
        elif self.display == "fb-headless":
            cmd.append("-display")
            cmd.append("none")
        elif self.display == "egl-headless":
            if qemu_version >= (6, 1, 0):
                cmd.append("-device")
                cmd.append("virtio-vga-gl")
            else:
                cmd.append("-vga")
                cmd.append("virtio")
            cmd.append("-display")
            cmd.append("egl-headless")
        else:
            raise ExecutionError(f"Unknown display '{self.display}'")  # type: ignore

        if self.nic:
            cmd.append("-nic")
            cmd.append(self.nic)

        if self.boot_args is not None:
            boot_args.append(self.boot_args)
        if self.kernel is not None and boot_args:
            cmd.append("-append")
            cmd.append(" ".join(boot_args))

        return cmd

    def on_activate(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self._cmd = self.get_qemu_base_args()

        self._cmd.append("-S")
        self._cmd.append("-qmp")
        self._cmd.append("stdio")

        self._cmd.append("-chardev")
        self._cmd.append(f"socket,id=serialsocket,host=0.0.0.0,port=54321,server=on,wait=off")
        self._cmd.append("-serial")
        self._cmd.append("chardev:serialsocket")

    def on_deactivate(self) -> None:
        assert self._socket

        if self.status:
            self.off()
        self._socket.close()
        self._socket = None

    @step()
    def on(self) -> None:
        """Start the QEMU subprocess, accept the unix socket connection and
        afterwards start the emulator using a QMP Command"""
        assert self._socket

        if self.status:
            return
        self.logger.info("Starting with: %s", " ".join(self._cmd))
        self._child_qemu = subprocess.Popen(self._cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        wait_for(lambda: is_port_in_use(54321), "port 54321 in use")

        if self.ser2net:
            self._child_ser2net = start_ser2net_mux(54321, 12345)
            wait_for(lambda: is_port_in_use(12345), "port 12345 in use")
            self._socket.connect(("localhost", 12345))
        else:
            self._socket.connect(("localhost", 54321))

        try:
            self.qmp = QMPMonitor(self._child_qemu.stdout, self._child_qemu.stdin)  # type: ignore
        except QMPError as exc:
            if self._child_qemu.poll() is not None:
                self._child_qemu.communicate()
                raise OSError(f"QEMU process terminated with exit code {self._child_qemu.returncode}") from exc
            raise

        self.status = 1

        # Restore port forwards
        for v in self._forwarded_ports.values():
            self._add_port_forward(*v)

        self.monitor_command("cont")
        if self.ser2net:
            time.sleep(1)
            self.sendline("")

    @step()
    def off(self) -> None:
        """Stop the emulator using a monitor command and await the exitcode"""
        if not self.status:
            return

        self.monitor_command("quit")
        kill_process(self._child_qemu)
        self._child_qemu = None

        kill_process(self._child_ser2net)
        self._child_ser2net = None

        self.status = 0

    def cycle(self) -> None:
        """Cycle the emulator by restarting it"""
        self.off()
        self.on()

    @step(result=True, args=["command", "arguments"])
    def monitor_command(self, command: str, arguments: dict | None = None) -> str:
        """Execute a monitor_command via the QMP"""
        if arguments is None:
            arguments = {}
        if not self.status:
            raise ExecutionError("Can't use monitor command on non-running target")  # type: ignore
        return self.qmp.execute(command, arguments)

    def _add_port_forward(
        self, proto: str, local_address: str, local_port: int, remote_address: str, remote_port: int
    ) -> None:
        self.monitor_command(
            "human-monitor-command",
            {"command-line": f"hostfwd_add {proto}:{local_address}:{local_port}-{remote_address}:{remote_port}"},
        )

    def add_port_forward(
        self, proto: str, local_address: str, local_port: int, remote_address: str, remote_port: int
    ) -> None:
        self._add_port_forward(proto, local_address, local_port, remote_address, remote_port)
        self._forwarded_ports[(proto, local_address, local_port)] = (
            proto,
            local_address,
            local_port,
            remote_address,
            remote_port,
        )

    def remove_port_forward(self, proto: str, local_address: str, local_port: int) -> None:
        del self._forwarded_ports[(proto, local_address, local_port)]
        self.monitor_command(
            "human-monitor-command",
            {"command-line": f"hostfwd_remove {proto}:{local_address}:{local_port}"},
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

    def _write(self, data) -> int:  # type: ignore
        assert self._socket

        return self._socket.send(data)

    def __str__(self) -> str:
        assert self.target
        return f"QemuDriver({self.target.name})"
