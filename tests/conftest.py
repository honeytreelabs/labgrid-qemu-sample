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

import pytest
from labgrid import Target
from labgrid.driver import ShellDriver, SSHDriver
from labgrid.strategy import Strategy


@pytest.fixture
def shell_command(target: Target, strategy: Strategy) -> ShellDriver:
    strategy.transition("shell")
    shell = target.get_driver("ShellDriver")
    return shell


@pytest.fixture
def ssh_command(target: Target, strategy: Strategy) -> SSHDriver:
    strategy.transition("shell")
    ssh = target.get_driver("SSHDriver")
    return ssh
