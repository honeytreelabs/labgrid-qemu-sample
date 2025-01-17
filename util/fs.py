import logging
import random
import string
import tempfile
from pathlib import Path

from labgrid.driver import ShellDriver, SSHDriver
from process import run


def create_temp_dir() -> Path:
    while True:
        # we don't need a super-secure cryptographic PRNG
        random_name = "".join(random.choices(string.ascii_letters + string.digits, k=12))  # noqa: S311
        temp_path = Path(tempfile.gettempdir()) / random_name
        logging.info(f"Creating temporary directory {temp_path}.")
        try:
            temp_path.mkdir(exist_ok=False)
            return temp_path
        except FileExistsError:
            continue


def mkdir(shell: ShellDriver | SSHDriver, path: Path | str) -> None:
    run(shell, f"mkdir -p {path}")


def sync(shell: ShellDriver | SSHDriver) -> None:
    run(shell, "sync")
