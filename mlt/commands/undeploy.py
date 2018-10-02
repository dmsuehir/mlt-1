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
import subprocess
import shutil

from mlt.commands import Command
from mlt.utils import (config_helpers, error_handling, files, process_helpers,
                       sync_helpers)


class UndeployCommand(Command):
    def __init__(self, args):
        super(UndeployCommand, self).__init__(args)
        self.config = config_helpers.load_config()

    def action(self):
        """deletes current kubernetes namespace"""

        if sync_helpers.get_sync_spec() is not None:
            error_handling.throw_error(
                "This app is currently being synced, please run "
                "`mlt sync delete` to unsync first", "red")

        namespace = self.config['namespace']
        jobs = files.get_deployed_jobs(job_names_only=True)
        if not jobs:
            error_handling.throw_error("This app has not been deployed yet.")
        else:
            if self.args.get('--job-name'):
                job_name = self.args['--job-name']
                if job_name in jobs:
                    self._undeploy_jobs(namespace, job_name)
                else:
                    error_handling.throw_error(
                        'Job name {} not found in: {}'.format(job_name, jobs))
            elif self.args.get('--all') or len(jobs) == 1:
                self._undeploy_jobs(namespace, jobs, all_jobs=True)
            else:
                error_handling.throw_error(
                    "Multiple jobs are found under this application, "
                    "please try `mlt undeploy --all` or specify a single "
                    "job to undeploy using "
                    "`mlt undeploy --job-name <job-name>`")

    def _undeploy_jobs(self, namespace, jobs, all_jobs=False):
        """undeploy the jobs passed to us
           jobs: 1 or more jobs to undeploy
           NOTE: right now there's no case in which some template has both
                 custom and not custom jobs because we check for custom job
                 by if there's a Makefile in the top level of the project
        """
        # simplify logic by `looping` over all jobs even if there's just 1
        if not isinstance(jobs, list):
            jobs = [jobs]

        # custom jobs require looping over all of them and calling
        # `make undeploy` on each job
        recursive_delete = False if files.is_custom('undeploy:') else True
        if recursive_delete:
            folder_to_delete = 'k8s'
            if not all_jobs:
                # only way all_jobs won't be false is if there's
                # a --job-name flag passed or there's only 1 job to undeploy
                if len(jobs) != 1:
                    error_handling.throw_error(
                        "There should be only 1 job to undeploy, "
                        "something went wrong. Please file a bug on "
                        "https://github.com/IntelAI/mlt")
                folder_to_delete = os.path.join(folder_to_delete, jobs[0])
            process_helpers.run(
                ["kubectl", "--namespace", namespace, "delete", "-f",
                 folder_to_delete, "--recursive"],
                raise_on_failure=True)
            # TODO: have this not be in a loop
            for job in jobs:
                self.remove_job_dir(os.path.join('k8s', job))
        else:
            for job in jobs:
                self._custom_undeploy(job)
                self.remove_job_dir(os.path.join('k8s', job))

    def remove_job_dir(self, job_dir):
        """remove the job sub-directory from k8s."""
        shutil.rmtree(job_dir)

    def _custom_undeploy(self, job_name):
        """
        Custom undeploy uses the make targets to perform operation.
        """
        # Adding USER env because
        # https://github.com/ksonnet/ksonnet/issues/298
        user_env = dict(os.environ, JOB_NAME=job_name, USER='root')
        try:
            output = subprocess.check_output(["make", "undeploy"],
                                             env=user_env,
                                             stderr=subprocess.STDOUT)
            print(output.decode("utf-8").strip())
        except subprocess.CalledProcessError as e:
            print("Error while undeploying app: {}".format(e.output))
