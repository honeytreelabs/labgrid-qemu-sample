import logging
import tempfile
from pathlib import Path

from crypto import generate_random_string
from labgrid.driver import ShellDriver, SSHDriver
from process import run


def create_temp_dir() -> Path:
    while True:
        random_name = generate_random_string(12)
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
