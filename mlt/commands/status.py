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
# Unless required by applicable law or agreed to in writing, software`
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: EPL-2.0
#

import json
import os
import subprocess

from mlt.commands import Command
from mlt.utils import config_helpers


class StatusCommand(Command):
    def __init__(self, args):
        super(StatusCommand, self).__init__(args)
        self.config = config_helpers.load_config()

    def action(self):
        with open('.push.json', 'r') as f:
            data = json.load(f)

        app_run_id = data.get('app_run_id', "")
        job_name = "-".join([self.config["name"], app_run_id])
        namespace = self.config['namespace']

        user_env = dict(os.environ, NAMESPACE=namespace, JOB_NAME=job_name)
        print(subprocess.check_output(["make status"],
                                      shell=True, env=user_env))
