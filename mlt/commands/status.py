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

import json

from mlt.commands import Command
from mlt.utils import config_helpers, process_helpers


class StatusCommand(Command):
    def __init__(self, args):
        super(StatusCommand, self).__init__(args)
        self.config = config_helpers.load_config()

    def action(self):
        pod_prefix = self._get_pod_name_prefix()
        namespace = self.config['namespace']

        output = process_helpers.run(["kubectl", "get", "pods", "--namespace",
                                      namespace, "-o", "wide", "-a"])

        output_lines = output.split("\n")
        filtered_pods = [line for line in output_lines
                         if line.startswith(pod_prefix)]

        if len(filtered_pods) > 0:
            # Print header row, followed by the pod list
            print(output_lines[0])

            for p in filtered_pods:
                print(p)
        else:
            print("No pods found with the following filter: \n"
                  "  Name prefix: {}\n  "
                  "  Namespace:   {}".format(pod_prefix, namespace))

    def _get_pod_name_prefix(self):
        with open('.push.json', 'r') as f:
            data = json.load(f)

        app_run_id = data.get('app_run_id', "").split("-")
        return "-".join([self.config["name"], app_run_id[0], app_run_id[1]])
