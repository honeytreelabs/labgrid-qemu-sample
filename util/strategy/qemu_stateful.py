import attr
from labgrid import target_factory

from .qemu_strategy import QEMUBaseStrategy


@target_factory.reg_driver
@attr.s(eq=False)
class QEMUStatefulStrategy(QEMUBaseStrategy):
    bindings = {
        "qemu": "StatefulQEMUDriver",
        "shell": "ShellDriver",
        "ssh": "SSHDriver",
    }

    def on(self) -> None:
        pass

    def off(self) -> None:
        pass
