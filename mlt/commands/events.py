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

import sys

from mlt.commands import Command
from mlt.utils import config_helpers, error_handling, files, process_helpers


class EventsCommand(Command):
    def __init__(self, args):
        super(EventsCommand, self).__init__(args)
        self.config = config_helpers.load_config()

    def action(self):
        """
        Display events for a job. If multiple jobs, specify with --job-name
        This method will check for `.push.json`
        and provides run-id to _get_event method to
        fetch events.
        """
        job = files.get_only_one_job(
            job_desired=self.args["--job-name"],
            error_msg="Please use --job-name flag to query for job events.")

        self._get_events(job, self.config['namespace'])

    def _get_events(self, filter_tag, namespace):
        """
         Fetches events
        """
        events_cmd = "kubectl get events --namespace {}".format(namespace)
        try:
            events = process_helpers.run_popen(events_cmd, shell=True)
            header_line = True
            header = events.stdout.readline()
            while True:
                output = events.stdout.readline().decode('utf-8')
                if output == '' and events.poll() is not None:
                    error = events.stderr.readline()
                    if error:
                        raise Exception(error)
                    break

                if output is not '' and filter_tag and filter_tag in output:
                    if header_line:
                        print(header.decode('utf-8'))
                        header_line = False
                    sys.stdout.write(output)
                    sys.stdout.flush()

            if header_line:
                print("No events to display for this job")
        except Exception as ex:
            if 'command not found' in str(ex):
                error_msg = "Please install `{}`. " + \
                    "It is a prerequisite for `mlt events` " + \
                    "to work".format(str(ex).split()[1])
            else:
                error_msg = "Exception: {}".format(ex)
            error_handling.throw_error(error_msg)
