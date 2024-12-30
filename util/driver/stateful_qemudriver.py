"""The QEMUDriver implements a driver to use a QEMU target"""

from labgrid.factory import target_factory

from .base_qemudriver import BaseQEMUDriver


@target_factory.reg_driver
class StatefulQEMUDriver(BaseQEMUDriver):
    pass
