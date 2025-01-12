import tempfile
from pathlib import Path

from labgrid.driver import SSHDriver


def put_file(ssh_command: SSHDriver, remote_path: Path, contents: bytes) -> None:
    with tempfile.NamedTemporaryFile() as temp:
        temp.write(contents)
        temp.flush()
        ssh_command.put(temp.name, str(remote_path))
