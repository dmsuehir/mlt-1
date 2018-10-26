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
import time
import pytest


from mlt.utils.process_helpers import run
from test_utils.e2e_commands import CommandTester


# NOTE: you need to deploy first before you deploy with --no-push
# otherwise you have no image to use to make new container from

class TestDeployFlow(CommandTester):
    @pytest.fixture(autouse=True, scope='function')
    def teardown(self):
        """Allow normal deployment, then undeploy and check status at end of
           every test. Also delete the namespace because undeploy doesn't
           do that.
        """
        try:
            # normal test execution
            yield
        finally:
            # no matter what, undeploy and check status
            try:
                self.undeploy_for_test_teardown()
                self.status(job_statuses=False)
            finally:
                # tear down namespace at end of test
                try:
                    run(["kubectl", "delete", "ns", self.namespace])
                except SystemExit:
                    # this means that the namespace and k8s resources are
                    # already deleted or were never created
                    pass

    # TODO: find a way to test `tensorboard-bm`.
    # `tensorboard-bm` template requires the user domain to be configured
    # as a custom parameter https://github.com/IntelAI/mlt/issues/371
    @pytest.mark.parametrize('template', filter(lambda x: os.path.isdir(
        os.path.join('mlt-templates', x))
        and ('tensorboard-bm' not in x), os.listdir('mlt-templates')))
    def test_deploying_templates(self, template):
        """tests every template in our mlt-templates dir"""
        self.init(template)
        self.build()
        self.deploy()

        # set the expected status for tensorboard templates as running, because
        # the pods stay alive (running) until the user kills the session.
        expected_status = "Running" if template == "tensorboard-gke" \
            else "Succeeded"

        self.verify_pod_status(expected_status=expected_status)
        self.status()
        self.events()

    def test_deploy_using_old_app(self):
        """ Test to ensure build/deploy/status of an old MLT v0.2.1 app
        works with the current MLT code. """
        old_app_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   "../old-mlt-app")
        self.init(existing_app_dir=old_app_dir)
        self.build()
        self.deploy()
        self.verify_pod_status()
        self.status()

    def test_deploy_enable_sync(self):
        self.init(enable_sync=True)
        self.build()
        self.deploy(sync=True)
        self.verify_pod_status(expected_status="Running")
        self.sync(create=True)
        self.status()
        self.sync(reload=True)
        self.status()
        self.sync(delete=True)

    def test_deploy_check_logs(self):
        """
        test deploying a template and then checking the logs to make sure the
        call doesn't crash
        """
        self.init()
        self.build()
        self.deploy()
        self.status()
        self.logs()
        self.status()
        self.deploy(logs=True, retries=300, no_push=True)
        self.verify_pod_status()

    def test_no_push_deploy(self):
        self.init()
        self.build()
        self.deploy()
        self.verify_pod_status()
        self.status()
        self.logs(use_job_name=True)
        self.events(use_job_name=True)
        self.deploy(no_push=True)
        self.verify_pod_status()
        self.status(count=2)
        self.undeploy(all_jobs=True)

    @pytest.mark.parametrize('template', ['hello-world', 'tf-distributed'])
    def test_interactive_deploy(self, template):
        """tests 2 templates with different pod numbers"""
        self.init(template)
        self.build()
        self.deploy()
        self.status()
        # we don't need the original deployment and it interferes with
        # picking the right tfjob pod to check
        self.undeploy(use_job_name=True)
        self.deploy(interactive=True, no_push=True, retries=60)
        self.verify_pod_status(expected_status="Running")
        self.status()

    def test_verbose_deploy_and_build(self):
        """tests hello-world template verbosely"""
        self.init()
        self.build(verbose=True)
        self.deploy(verbose=True)
        self.verify_pod_status()
        self.status()

    def test_watch_build_and_deploy_no_push(self):
        self.init()
        self.build(watch=True)
        self.deploy()
        self.verify_pod_status()
        self.status()
        self.deploy(no_push=True)
        self.verify_pod_status()
        self.status(count=2)
        self.undeploy(all_jobs=True)

    def test_debug_wrapper(self):
        """tests debug_on_fail param"""
        # Update configs to enable debug_on_fail
        self.init()
        self.config(subcommand="set",
                    config_name="template_parameters.debug_on_fail",
                    config_value="True")

        # Edit to insert an error
        main_file = os.path.join(self.project_dir, "main.py")
        with open(main_file, "a") as fh:
            fh.write("raise ValueError()\n")

        self.build()
        # Pod should still be running instead of going to 'Succeeded'
        # since debug is enabled and we inserted an error
        self.deploy()
        self.verify_pod_status(expected_status="Running")

        # Pod should still be running to allow user to debug
        time.sleep(5)
        mlt_status = self.status()
        assert "Running" in mlt_status
        self.undeploy(use_job_name=True)

        # Try again with debug disabled
        self.config(subcommand="set",
                    config_name="template_parameters.debug_on_fail",
                    config_value="False")
        self.deploy(no_push=True)
        self.verify_pod_status(expected_status="Failed")
