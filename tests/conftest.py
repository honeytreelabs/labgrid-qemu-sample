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

import json
from ipaddress import IPv4Address

import pytest
from labgrid import Target
from labgrid.driver import ShellDriver, SSHDriver
from labgrid.strategy import Strategy
from process import bash_run


@pytest.fixture
def primary_host_ip() -> IPv4Address:
    ip_cfg_str = bash_run("ip -4 -json r s")
    ip_cfg = json.loads(ip_cfg_str)
    primary_ip = ip_cfg[0]["prefsrc"]
    return IPv4Address(primary_ip)


def shell_command(target: Target, strategy: Strategy) -> ShellDriver:
    strategy.transition("shell")
    shell = target.get_driver("ShellDriver")
    return shell


@pytest.fixture
def ssh_command(target: Target, strategy: Strategy) -> SSHDriver:
    strategy.transition("shell")
    ssh = target.get_driver("SSHDriver")
    return ssh
