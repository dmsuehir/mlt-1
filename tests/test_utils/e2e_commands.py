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
"""
This file will contain a command class for easy testing of different
e2e scenarios by other test files. Goal is to make it easy to add further
e2e scenarios in the future with the least amount of code duplication.
"""
import getpass
import json
import os
import time
import uuid
from subprocess import check_output, PIPE, Popen

from mlt.utils.process_helpers import run, run_popen
from project import basedir


class CommandTester(object):
    def __init__(self, workdir):
        # just in case tests fail, want a clean namespace always
        self.workdir = workdir
        self.registry = os.getenv('MLT_REGISTRY', 'localhost:5000')
        self.registry_catalog_call = self._fetch_registry_catalog_call()
        # putting an `a` here because PytorchJob requires a letter in front
        # it tries to create a service based on image name
        self.app_name = 'a' + str(uuid.uuid4())[:8]
        self.namespace = getpass.getuser() + '-' + self.app_name

        self.project_dir = os.path.join(self.workdir, self.app_name)
        self.mlt_json = os.path.join(self.project_dir, 'mlt.json')
        self.build_json = os.path.join(self.project_dir, '.build.json')
        self.deploy_json = os.path.join(self.project_dir, '.push.json')
        self.train_file = os.path.join(self.project_dir, 'main.py')

        # ANY NEW TFJOBS NEED TO HAVE THEIR TEMPLATE NAMES LISTED HERE
        # TFJob terminates pods after completion so can't check old pods
        # for status of job completion
        self.tfjob_templates = ('tf-dist-mnist', 'tf-distributed')

    def _fetch_registry_catalog_call(self):
        """returns either a local registry curl call or one for gcr"""
        if 'gcr' in self.registry:
            gcr_token = run_popen("gcloud auth print-access-token",
                                  shell=True).stdout.read().decode(
                "utf-8").strip()
            catalog_call = 'curl -v -u _token:{} '.format(
                gcr_token) + '"https://gcr.io/v2/_catalog"'
        else:
            catalog_call = 'curl --noproxy \"*\" registry:5000/v2/_catalog'
        return catalog_call

    def _grab_latest_pod_or_tfjob(self):
        """grabs latest pod by startTime"""
        if self.template in self.tfjob_templates:
            # NOTE: do we need some sort of time filter here too?
            obj_string = "kubectl get tfjob -a --namespace {} -o json".format(
                self.namespace)
        else:
            obj_string = "kubectl get pods -a --namespace {}".format(
                self.namespace) + " --sort-by=.status.startTime -o json"
        objs = run_popen(obj_string, shell=True).stdout.read().decode('utf-8')
        if objs:
            objs = json.loads(objs).get('items')[-1]['status']
            # tfjob is special and puts the `Succeeded` status on the `state`
            # rather than the `phase` like everything else
            return objs["state"] if "tfjob" in obj_string else objs["phase"]
        else:
            raise ValueError("No pod(s) deployed to namespace {}".format(
                self.namespace))

    def init(self, template='hello-world', template_repo=basedir()):
        p = Popen(
            ['mlt', 'init', '--registry={}'.format(self.registry),
             '--template-repo={}'.format(template_repo),
             '--namespace={}'.format(self.namespace),
             '--template={}'.format(template), self.app_name],
            cwd=self.workdir)
        # keep track of template we created so we can check if it's a TFJob
        # that terminates pods after completion so we need to check the crd
        # for status on if job was successful
        self.template = template
        assert p.wait() == 0
        assert os.path.isfile(self.mlt_json)
        with open(self.mlt_json) as f:
            standard_configs = {
                'namespace': self.namespace,
                'name': self.app_name,
                'registry': self.registry
            }
            actual_configs = json.loads((f.read()))
            assert dict(actual_configs, **standard_configs) == actual_configs
        # verify we created a git repo with our project init
        assert "On branch master" in run(
            "git --git-dir={}/.git --work-tree={} status".format(
                self.project_dir, self.project_dir).split())

    def config(self, subcommand="list", config_name=None, config_value=None):
        command = ['mlt', 'config', subcommand]

        if config_name:
            command.append(config_name)

        if config_value:
            command.append(config_value)

        p = Popen(command, cwd=self.project_dir, stdout=PIPE)
        output, err = p.communicate()
        assert p.wait() == 0

        if subcommand == "list":
            assert output

        assert err is None
        return output, err

    def build(self, watch=False):
        build_cmd = ['mlt', 'build']
        if watch:
            build_cmd.append('--watch')

        build_proc = Popen(build_cmd, cwd=self.project_dir)

        if watch:
            # ensure that `mlt build --watch` has started
            time.sleep(1)
            # we need to simulate our training file changing
            run_popen("echo \"print('hello')\" >> {}".format(
                self.train_file), shell=True).wait()
            # wait for 30 seconds (for timeout) or until we've built our image
            # then kill the build proc or it won't terminate
            start = time.time()
            while not os.path.exists(self.build_json):
                time.sleep(1)
                if time.time() - start >= 30:
                    break
            build_proc.kill()
        else:
            assert build_proc.wait() == 0

        assert os.path.isfile(self.build_json)
        with open(self.build_json) as f:
            build_data = json.loads(f.read())
            assert 'last_container' in build_data and \
                   'last_build_duration' in build_data
            # verify that we created a docker image
            assert run_popen(
                "docker image inspect {}".format(build_data['last_container']),
                shell=True, stdout=None, stderr=None
            ).wait() == 0

    def deploy(self, no_push=False, interactive=False):
        deploy_cmd = ['mlt', 'deploy']
        if no_push:
            deploy_cmd.append('--no-push')
        if interactive:
            deploy_cmd.append('--interactive')
        p = Popen(deploy_cmd, cwd=self.project_dir)
        out, err = p.communicate()
        assert p.wait() == 0

        if not no_push:
            assert os.path.isfile(self.deploy_json)
            with open(self.deploy_json) as f:
                deploy_data = json.loads(f.read())
                assert 'last_push_duration' in deploy_data and \
                       'last_remote_container' in deploy_data
            # verify that the docker image has been pushed to our registry
            # need to decode because in python3 this output is in bytes
            assert 'true' in run_popen(
                "{} | jq .repositories | jq 'contains([\"{}\"])'".format(
                    self.registry_catalog_call, self.app_name),
                shell=True).stdout.read().decode("utf-8")

        self._verify_pod_success(interactive)

    def status(self):
        status_cmd = ['mlt', 'status']
        p = Popen(status_cmd, cwd=self.project_dir, stdout=PIPE)
        output, err = p.communicate()
        assert p.wait() == 0

        # verify that we have some output, and no errors
        assert output
        assert err is None

    def undeploy(self):
        p = Popen(['mlt', 'undeploy'], cwd=self.project_dir)
        assert p.wait() == 0
        # verify no more deployment job
        assert run_popen(
            "kubectl get jobs --namespace={}".format(
                self.namespace), shell=True).wait() == 0

    def _verify_pod_success(self, interactive_deploy):
        """verify that our latest job did indeed get deployed to k8s"""
        # TODO: probably refactor this function
        # allow for 60 seconds for the pod to start creating;
        # pytorch operator causes pods to fail for a bit before success
        # which is out of our hands
        start = time.time()
        pod_status = None
        while pod_status is None:
            try:
                pod_status = self._grab_latest_pod_or_tfjob()
            except (ValueError, IndexError):
                # if no pod is available, or pods is an empty dict, ignore
                # for 1 min
                time.sleep(1)
                if time.time() - start >= 60:
                    break

        # wait for pod to finish, up to 3 min for pending and 5 for running
        # not counting interactive that will always be running
        start = time.time()
        while pod_status == 'Pending':
            time.sleep(1)
            pod_status = self._grab_latest_pod_or_tfjob()
            if time.time() - start >= 180:
                break

        # interactive pods are `sleep; infinity` so will still be running
        if not interactive_deploy:
            while pod_status == 'Running':
                time.sleep(1)
                pod_status = self._grab_latest_pod_or_tfjob()
                if time.time() - start >= 480:
                    break
            assert pod_status == 'Succeeded'
        else:
            assert pod_status == 'Running'
