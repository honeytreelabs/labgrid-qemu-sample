"""The QEMUDriver implements a driver to use a QEMU target"""

import atexit
import re
import select
import shlex
import socket
import subprocess
import time

import attr
from func import wait_for
from labgrid.driver import Driver
from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
from labgrid.driver.exception import ExecutionError
from labgrid.factory import target_factory
from labgrid.protocol import ConsoleProtocol, PowerProtocol
from labgrid.step import step
from network import is_port_in_use
from pexpect import TIMEOUT
from process import kill_process
from qmp import QMPMonitor

from driver.params import get_qmp_port

from .base_qemudriver import BaseQEMUDriver


def start_ser2net_mux(port_conn: int, port_accept: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            "/usr/sbin/ser2net",
            "-n",
            "-d",
            "-Y",
            "connection: &con01",
            "-Y",
            f"  connector: tcp,localhost,{port_conn}",
            "-Y",
            f"  accepter: tcp,localhost,{port_accept}",
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
class CustomQEMUDriver(BaseQEMUDriver, ConsoleExpectMixin, Driver, PowerProtocol, ConsoleProtocol):
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

    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        self.status: int = 0
        self._child_qemu: subprocess.Popen | None = None
        self._child_ser2net: subprocess.Popen | None = None
        atexit.register(self._atexit)

    def _atexit(self) -> None:
        kill_process(self._child_ser2net)
        self._child_ser2net = None
        kill_process(self._child_qemu)
        self._child_qemu = None

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

        cmd.append("-S")  # freeze CPU at startup

        cmd.append("-qmp")
        # cmd.append("stdio")
        cmd.append(f"tcp:localhost:{get_qmp_port()},server=on,wait=off")

        cmd.append("-chardev")
        cmd.append("socket,id=serialsocket,host=0.0.0.0,port=54321,server=on,wait=off")
        cmd.append("-serial")
        cmd.append("chardev:serialsocket")

        return cmd

    @step()
    def on(self) -> None:
        """Start the QEMU subprocess, accept the unix socket connection and
        afterwards start the emulator using a QMP Command"""

        if self.status:
            return
        cmd = self.get_qemu_base_args()
        self.logger.info("Starting with: %s", " ".join(cmd))
        self._child_qemu = subprocess.Popen(cmd)  # , stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        wait_for(lambda: is_port_in_use(54321), "port 54321 in use")

        self._child_ser2net = start_ser2net_mux(54321, 12345)
        wait_for(lambda: is_port_in_use(12345), "port 12345 in use")

        self.status = 1

        self.monitor_command("cont")

    @step()
    def off(self) -> None:
        """Stop the emulator using a monitor command and await the exitcode"""
        if not self.status:
            return

        kill_process(self._child_ser2net)
        self._child_ser2net = None

        self.monitor_command("quit")
        kill_process(self._child_qemu)
        self._child_qemu = None

        self.status = 0

    def cycle(self) -> None:
        """Cycle the emulator by restarting it"""
        self.off()
        self.on()

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
