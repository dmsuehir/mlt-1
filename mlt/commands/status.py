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
import os
import subprocess
from datetime import datetime
from pytz import timezone

from mlt.commands import Command
from mlt.utils import (config_helpers, error_handling, files, process_helpers,
                       sync_helpers)


class StatusCommand(Command):
    def __init__(self, args):
        super(StatusCommand, self).__init__(args)
        self.config = config_helpers.load_config()

    def action(self):
        if not os.path.isfile('.push.json'):
            error_handling.throw_error("This app has not been deployed yet")

        namespace = self.config['namespace']
        jobs = files.get_deployed_jobs()[:self.args["<count>"]]

        # display status for only `--count` amount of jobs
        for job in jobs:
            job_name = job.replace('k8s/', '')
            print('Job: {} -- Creation Time: {}'.format(
                # replacing tzinfo with UTC to print `+0000` so users know
                # output is in utc
                # TODO: better way to print this?
                job_name, datetime.utcfromtimestamp(
                    int(os.path.getmtime(job))).replace(
                    tzinfo=timezone('UTC'))))
            self._display_status(job_name, namespace)
            # TODO: something more fancy to separate different statuses?
            print('')

        if len(jobs) == 0:
            print("No jobs are deployed.")

    def _display_status(self, job, namespace):
        """detects what kind of job was deployed and calls the correct
           status display function
        """
        status_options = {
            "job": self._generic_status,
            "tfjob": self._crd_status,
            "pytorchjob": self._crd_status,
            # experiments have yaml templates but also a bash script to call
            "experiment": self._custom_status
        }

        # if we have more than 1 k8 object created and types don't match
        # go with a custom job type since we won't know what kubectl call
        # to make to get status from everything
        # also, if `status:` in Makefile we'll assume it's custom always
        job_types, all_same_job_type = files.get_job_kinds()
        if (job_types and not all_same_job_type) or files.is_custom('status:'):
            job_types = "custom"
        elif job_types:
            job_types = job_types.pop()

        try:
            status_options.get(job_types, self._custom_status)(
                job, namespace, job_types)
        except subprocess.CalledProcessError as e:
            if "No rule to make target `status'" in str(e.output):
                # TODO: when we have a template updating capability, add a
                # note recommending that he user update's their template to
                # get the status command
                error_msg = "This app does not support the `mlt status` " + \
                    "command. No `status` target was found in the Makefile."
            else:
                error_msg = "Error while getting app status: {}".format(
                    e.output)
            error_handling.throw_error(error_msg)

    def _custom_status(self, job, namespace, job_type):
        """runs `make status` on any special deployment
           Special deployment is defined as any one of the following:
                1. Doesn't have deployment yaml
                2. Has deployment yaml but many deployments of different kinds
        """
        user_env = dict(os.environ, NAMESPACE=namespace, JOB_NAME=job)
        output = subprocess.check_output(["make", "status"],
                                         env=user_env,
                                         stderr=subprocess.STDOUT)
        print(output.decode("utf-8").strip())
        if sync_helpers.get_sync_spec() is not None:
            # format the string before passing it print so that the string
            # is evaluated correctly
            print("\nSYNC STATUS\n{}".format(
                'This app is being watched by sync'))

    def _generic_status(self, job, namespace, job_type):
        """displays simple pod information"""
        status = process_helpers.run_popen(
            ["kubectl", "get", "pods", "--namespace", namespace,
             "-o", "wide", "-a", "-l", "job-name={}".format(job)],
            stdout=True, stderr=True)
        status.wait()

    def _crd_status(self, job, namespace, job_type):
        """Handles statuses for various crd deployments
           CRDs handled:
                1. TFJob
                2. PyTorchJob
        """
        label = 'tf_job_name' if job_type == 'tfjob' else 'pytorch_job_name'

        print("CRD: {}".format(job_type.upper()))
        status = process_helpers.run_popen(
            ["kubectl", "get", job_type, job, "--namespace", namespace])
        out, err = status.communicate()
        if status.wait() != 0:
            print("The job may have been undeployed.")
        else:
            print(out.decode('utf-8'))

        print("Pods: ")
        status = process_helpers.run_popen(
            ["kubectl", "get", "pods", "--namespace", namespace, "-o", "wide",
             "-a", "-l", "{}={}".format(label, job)], stdout=True, stderr=True)
        status.communicate()
