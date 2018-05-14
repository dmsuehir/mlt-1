#
# -*- coding: utf-8 -*-
#
# Copyright (c) 2018 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: EPL-2.0
#
import os
import pytest

from test_utils.e2e_commands import CommandTester
from test_utils.files import create_work_dir


# NOTE: you need to deploy first before you deploy with --no-push
# otherwise you have no image to use to make new container from

@pytest.mark.parametrize('template',
                         filter(lambda x: os.path.isdir(
                             os.path.join('mlt-templates', x)),
                             os.listdir('mlt-templates')))
def test_deploying_templates(template):
    with create_work_dir() as workdir:
        commands = CommandTester(workdir)
        commands.init(template)
        commands.build()
        commands.deploy()
        commands.status()
        commands.undeploy()
        commands.status()


def test_no_push_deploy():
    with create_work_dir() as workdir:
        commands = CommandTester(workdir)
        commands.init()
        commands.build()
        commands.deploy()
        commands.status()
        commands.deploy(no_push=True)
        commands.status()
        commands.undeploy()
        commands.status()


def test_watch_build_and_deploy_no_push():
    with create_work_dir() as workdir:
        commands = CommandTester(workdir)
        commands.init()
        commands.build(watch=True)
        commands.deploy()
        commands.status()
        commands.deploy(no_push=True)
        commands.status()
        commands.undeploy()
        commands.status()
