import logging
import sys

from labgrid import Environment
from strategy import QEMUNetworkStrategy


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("cli")

    env = Environment("./config/qemu.yaml")  # type: ignore
    target = env.get_target()
    if target is None:
        logger.error("Could not obtain target")
        sys.exit(1)

    qemu_strategy: QEMUNetworkStrategy = target.get_strategy()
    qemu_strategy.transition("shell")
    breakpoint()
    qemu_strategy.transition("off")


if __name__ == "__main__":
    main()
