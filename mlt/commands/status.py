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
import sys

from mlt.commands import Command
from mlt.utils import config_helpers


class StatusCommand(Command):
    def __init__(self, args):
        super(StatusCommand, self).__init__(args)
        self.config = config_helpers.load_config()

    def action(self):
        push_file = '.push.json'
        if os.path.isfile(push_file):
            with open(push_file, 'r') as f:
                data = json.load(f)
        else:
            print("This application has not been deployed yet.")
            sys.exit(1)

        app_run_id = data.get('app_run_id', "")
        job_name = "-".join([self.config["name"], app_run_id])
        namespace = self.config['namespace']
        user_env = dict(os.environ, NAMESPACE=namespace, JOB_NAME=job_name)

        try:
            output = subprocess.check_output(["make status"], shell=True,
                                             env=user_env,
                                             stderr=subprocess.STDOUT)
            print(output.decode("utf-8").strip())
        except subprocess.CalledProcessError as e:
            if "No rule to make target `status'" in str(e.output):
                # App doesn't have the status target in the Makefile
                print(StatusCommand._default_status(
                    namespace, self.config["name"], app_run_id))
            else:
                print("Error while getting app status: {}".format(e.output))

    @staticmethod
    def _default_status(namespace, app_name, app_run_id):
        """ 
        Default status method, for when the app's Makefile doesn't have
        a status target defined.
        """
        run_id_list = app_run_id.split("-")

        if len(run_id_list) < 2:
            ValueError("Unable to get job status because the run id {}"
                       "is invalid".format(app_run_id))

        # Pod name prefix for filtering (we can't filter by pod label, since
        # the label name is different depending on job type)
        pod_name_prefix = "-".join([app_name, run_id_list[0], run_id_list[1]])

        # Get pods list and display it
        cmd = "kubectl get pods -a -o wide --namespace {} | " \
              "awk 'NR==1 || /{}/'".format(namespace, pod_name_prefix)
        output = subprocess.check_output([cmd], shell=True,
                                         stderr=subprocess.STDOUT)
        output = output.decode("utf-8").strip()

        if output.count("\n") == 0:
            output = "No pods found for job: {}".format(
                "-".join([app_name, app_run_id]))
        return output
