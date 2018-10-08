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
import time
import uuid
from watchdog.observers import Observer

from mlt.commands import Command
from mlt.event_handler import EventHandler
from mlt.utils import (config_helpers, error_handling, files, progress_bar,
                       process_helpers, schema)


class BuildCommand(Command):
    def __init__(self, args):
        super(BuildCommand, self).__init__(args)
        self.config = config_helpers.load_config()

    def action(self):
        """creates docker images
           if `--watch` is passed, continually will build on change
        """
        self._watch_and_build() if self.args['--watch'] else self._build()

    def _build(self):
        last_build_duration = files.fetch_action_arg(
            'build', 'last_build_duration')

        schema.validate()

        started_build_time = time.time()

        container_name = "{}:{}".format(self.config['name'], uuid.uuid4())
        print("Starting build {}".format(container_name))

        template_parameters = config_helpers.\
            get_template_parameters(self.config)

        params = ""
        for key, val in template_parameters.items():
            params += "{}={} ".format(key.upper(), val)

        build_cmd = "CONTAINER_NAME={} {}make build".format(
            container_name, params)

        if self.args['--verbose']:
            build_process = process_helpers.run_popen(build_cmd,
                                                      shell=True,
                                                      stdout=True,
                                                      stderr=True)
        else:
            build_process = process_helpers.run_popen(build_cmd,
                                                      shell=True)
            with process_helpers.prevent_deadlock(build_process):
                progress_bar.duration_progress(
                    'Building {}'.format(
                        self.config["name"]), last_build_duration,
                    lambda: build_process.poll() is not None)
        if build_process.poll() != 0:
            # When we have an error, get the stdout and error output
            # and display them both with the error output in red.
            output, error_msg = build_process.communicate()
            if output:
                print(output.decode("utf-8"))
            if error_msg:
                error_handling.throw_error(error_msg.decode("utf-8"), 'red')

        built_time = time.time()

        # Write last container to file
        with open('.build.json', 'w') as f:
            f.write(json.dumps({
                "last_container": container_name,
                "last_build_duration": built_time - started_build_time
            }))

        print("Built {}".format(container_name))

    def _watch_and_build(self):
        event_handler = EventHandler(self._build)
        observer = Observer()
        observer.schedule(event_handler, './', recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            observer.stop()
        observer.join()
