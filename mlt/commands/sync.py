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
import os
import subprocess

from mlt.commands import Command
from mlt.utils import (config_helpers, error_handling, sync_helpers)


class SyncCommand(Command):
    def __init__(self, args):
        super(SyncCommand, self).__init__(args)
        self.config = config_helpers.load_config()

    def action(self):
        if not os.path.isfile('.stignore'):
            error_handling.throw_error(
                "This app is not initialized with '--enable-sync' option")

        push_file = '.push.json'
        if not os.path.isfile(push_file):
            error_handling.throw_error("This app has not been deployed yet")

        # Call the specified sub-command
        if self.args.get('create'):
            self._create()
        elif self.args.get('reload'):
            self._reload()
        else:
            self._delete()

    def _create(self):
        push_file = '.push.json'
        with open(push_file, 'r') as f:
            push_data = json.load(f)

        if sync_helpers.get_sync_spec() is not None:
            error_handling.throw_error(
                "Syncing spec has been already created for this app")

        app_run_id = push_data.get('app_run_id', "")
        job_name = '-'.join([self.config["name"], app_run_id])
        namespace = self.config['namespace']
        user_env = dict(os.environ, SYNC_SPEC=job_name, NAMESPACE=namespace,
                        JOB_NAME=job_name)
        try:
            subprocess.check_output(["make", "sync-create"], env=user_env,
                                    stderr=subprocess.STDOUT)
            with open('.sync.json', 'w') as json_file:
                sync_data = {'sync_spec': job_name}
                json.dump(sync_data, json_file, indent=2)
            print("Syncing spec is created successfully")
        except subprocess.CalledProcessError as e:
            if "No rule to make target `sync-create'" in str(e.output):
                # TODO: when we have a template updating capability, add a
                # note recommending that he user update's their template to
                # get the sync create command
                print("This app does not support the `mlt sync create` "
                      "command. No `sync-create` target was found in the "
                      "Makefile.")
            else:
                print("Error while creating sync spec: {}".format(e.output))

    def _reload(self):
        sync_spec = sync_helpers.get_sync_spec()
        if sync_spec is None:
            error_handling.throw_error(
                "No syncing spec has been created for this app yet")

        user_env = dict(os.environ, SYNC_SPEC=sync_spec)

        try:
            subprocess.check_output(["make", "sync-reload"], env=user_env,
                                    stderr=subprocess.STDOUT)
            print("Sync agent is restarted")
        except subprocess.CalledProcessError as e:
            if "No rule to make target `sync-reload'" in str(e.output):
                # TODO: when we have a template updating capability, add a
                # note recommending that he user update's their template to
                # get the sync reload command
                print("This app does not support the `mlt sync reload` "
                      "command. No `sync-reload` target was found in the "
                      "Makefile.")
            elif "{} does not exist. Did you mean something else".format(
                    sync_spec) in str(e.output):
                print("Syncing spec has not been created for this app yet")
            else:
                print("Error while reloading sync agent: {}".format(e.output))

    def _delete(self):
        sync_spec = sync_helpers.get_sync_spec()
        if sync_spec is None:
            error_handling.throw_error(
                "No syncing spec has been created for this app yet")

        user_env = dict(os.environ, SYNC_SPEC=sync_spec)

        try:
            subprocess.check_output(["make", "sync-delete"], env=user_env,
                                    stderr=subprocess.STDOUT)
            with open('.sync.json', 'r+') as json_file:
                sync_data = json.load(json_file)
                if 'sync_spec' in sync_data.keys():
                    del(sync_data['sync_spec'])
                json_file.seek(0)
                json.dump(sync_data, json_file, indent=2)
                json_file.truncate()
            print("Syncing spec is successfully deleted")
        except subprocess.CalledProcessError as e:
            if "No rule to make target `sync-delete'" in str(e.output):
                # TODO: when we have a template updating capability, add a
                # note recommending that he user update's their template to
                # get the sync delete command
                print("This app does not support the `mlt sync delete` "
                      "command. No `sync-delete` target was found in the "
                      "Makefile.")
            elif "{} does not exist. Did you mean something else".format(
                    sync_spec) in str(e.output):
                print("No syncing spec has been created for this app yet")
            else:
                print("Error while deleting syncing spec: {}".format(e.output))
