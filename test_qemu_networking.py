# Copyright 2023 by Garmin Ltd. or its subsidiaries
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

from labgrid.driver import ShellDriver, SSHDriver


def run(shell: ShellDriver | SSHDriver, cmd: str) -> str:
    return "\n".join(shell.run_check(cmd))


def test_shell(shell_command: ShellDriver):
    run(shell_command, "true")

    logging.info(run(shell_command, "uname -a"))

    assert run(shell_command, "uname -n") == "OpenWrt"
    assert run(shell_command, "uname -s") == "Linux"
    assert run(shell_command, "uname -m") == "x86_64"


def test_ssh(ssh_command: SSHDriver):
    ssh_command.run("true")
