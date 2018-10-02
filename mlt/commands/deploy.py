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
import time
import uuid
import yaml
from string import Template
from subprocess import CalledProcessError, check_output, STDOUT
from termcolor import colored

from mlt.commands import Command
from mlt.utils import (build_helpers, config_helpers, error_handling, files,
                       kubernetes_helpers, progress_bar,
                       process_helpers, log_helpers, schema,
                       sync_helpers)


class DeployCommand(Command):
    def __init__(self, args):
        super(DeployCommand, self).__init__(args)
        self.config = config_helpers.load_config()
        build_helpers.verify_build(self.args)

    def action(self):
        schema.validate()
        if sync_helpers.get_sync_spec() is not None:
            print(colored("This folder is currently being synced, please run "
                          "`mlt sync delete {}` to delete sync spec "
                          "manually".format(sync_helpers.get_sync_spec()),
                          'yellow'))

        skip_crd_check = self.args['--skip-crd-check']
        if not skip_crd_check:
            kubernetes_helpers.check_crds(exit_on_failure=True)

        if self.args['--no-push']:
            print("Skipping image push")
        else:
            self._push()

        self._deploy_new_container()

        if self.args["--logs"]:
            self._tail_logs()

    def _push(self):
        self.container_name = files.fetch_action_arg(
            'build', 'last_container')

        self.started_push_time = time.time()
        self._push_docker()

        if not self.args['--verbose']:
            self._poll_docker_proc()

        with open('.push.json', 'w') as f:
            f.write(json.dumps({
                "last_remote_container": self.remote_container_name,
                "last_push_duration": time.time() - self.started_push_time
            }))

        print("Pushed {} to {}".format(
            self.config["name"], self.remote_container_name))

    def _push_docker(self):
        self.remote_container_name = "{}/{}".format(
            self.config['registry'], self.container_name)
        self._tag()

        push_cmd = ["docker", "push", self.remote_container_name]
        if self.args['--verbose']:
            self.push_process = process_helpers.run_popen(
                push_cmd, stdout=True, stderr=True)
            self.push_process.wait()
            # add newline to separate push output from container deploy output
            print('')
        else:
            self.push_process = process_helpers.run_popen(push_cmd)

    def _poll_docker_proc(self):
        """used only in the case of non-verbose deploy mode to dump loading
           bar and any error that happened
        """
        last_push_duration = files.fetch_action_arg(
            'push', 'last_push_duration')
        with process_helpers.prevent_deadlock(self.push_process):
            progress_bar.duration_progress(
                'Pushing {}'.format(self.config["name"]), last_push_duration,
                lambda: self.push_process.poll() is not None)

        # If the push fails, get stdout/stderr messages and display them
        # to the user, with the error message in red.
        if self.push_process.poll() != 0:
            push_stdout, push_error = self.push_process.communicate()
            print(push_stdout.decode("utf-8"))
            error_handling.throw_error(push_error.decode("utf-8"), 'red')

    def _tag(self):
        process_helpers.run(
            ["docker", "tag", self.container_name, self.remote_container_name])

    @staticmethod
    def _update_app_run_id(app_run_id):
        with open('.push.json', 'r+') as json_file:
            data = json.load(json_file)
            data['app_run_id'] = app_run_id
            json_file.seek(0)
            json.dump(data, json_file, indent=2)
            json_file.truncate()

    def _deploy_new_container(self):
        """Substitutes image, app, run data into k8s-template selected.
           Can also launch user into interactive shell with --interactive flag
        """
        app_name = self.config['name']
        self.namespace = self.config['namespace']
        remote_container_name = files.fetch_action_arg(
            'push', 'last_remote_container')
        if remote_container_name is None:
            raise ValueError("No image found to deploy with. Run a plain "
                             "`mlt deploy` to fix this. Most common reason "
                             "for this is a --no-push was used before "
                             "any image was available to use.")

        print("Deploying {}".format(remote_container_name))
        kubernetes_helpers.ensure_namespace_exists(self.namespace)

        app_run_id = str(uuid.uuid4())
        """
        we'll keep track of the number of containers that would be deployed
        so we know if we should exec into 1 or not (only auto-exec if 1 made)
        if we have replicas (with value > 1) then we automatically won't
        go into most recent pod, because there will be > 1 container made
        if we find > 1 container regardless of replica, same logic applies
        """
        self._replicas_found = False
        self._total_containers = 0

        # deploy our normal template sub logic, then if `deploy` in Makefile
        # add whatever custom stuff is desired
        self._default_deploy(app_name=app_name,
                             app_run_id=app_run_id,
                             remote_container_name=remote_container_name)
        if files.is_custom("deploy:"):
            # execute the custom deploy code
            self._custom_deploy(app_name=app_name,
                                app_run_id=app_run_id,
                                remote_container_name=remote_container_name)

        self._update_app_run_id(app_run_id)
        print("\nInspect created objects by running:\n"
              "$ kubectl get --namespace={} all\n"
              "or \n$ mlt status\n".format(self.namespace))

        if self.args["--interactive"] and not self._replicas_found \
                and self._total_containers == 1:
            self._exec_into_pod(self._get_most_recent_podname())
        elif self.args["--interactive"]:
            print("More than one container created."
                  ".\nCall `kubectl exec -it {{pod_name_here}} "
                  "--namespace={} /bin/bash` on a `Running` pod NAME "
                  "below.\nIf no pods are running yet, run `mlt status` "
                  "occasionally, or `watch -n1 mlt status` to watch until "
                  "pods are `Running`.\n".format(self.namespace))

            for line in self._get_pods_by_start_time():
                print(line)

    def _default_deploy(self, app_name, app_run_id, remote_container_name):
        """do template substitution across everything in `k8s-templates` dir
           replaces things with $ with the vars from template.substitute
           also patches deployment if interactive mode is set
        """
        for path, dirs, filenames in os.walk("k8s-templates"):
            for filename in filenames:
                with open(os.path.join(path, filename)) as f:
                    template = Template(f.read())
                out = template.substitute(
                    image=remote_container_name,
                    app=app_name, run=app_run_id, namespace=self.namespace,
                    **config_helpers.get_template_parameters(self.config))

                # some templates are still in yaml form by the time they reach
                # this point, so ignore a ValueError due to no json obj avail
                try:
                    out = self._ensure_correct_data_types(json.loads(out))
                except ValueError:
                    pass

                if self.args["--interactive"]:
                    # every pod will be made to `sleep infinity & wait`
                    out = self._patch_template_spec(out)
                self._apply_template(out, filename, app_name, app_run_id)

    def _ensure_correct_data_types(self, template_json):
        """Due to us editing the yaml now in init.py as well, we have some
           values that get turned into strings that kubernetes expects to be
           integers.
           TODO: move all template logic to deploy.py so this isn't needed
        """
        if "replicaSpecs" in template_json:
            for spec in template_json["replicaSpecs"]:
                spec["replicas"] = int(spec["replicas"])
        for k, v in template_json.items():
            if isinstance(v, dict):
                v = self._ensure_correct_data_types(v)
        return json.dumps(template_json, indent=2)

    def _custom_deploy(self, app_name, app_run_id, remote_container_name):
        job_name = "-".join([app_name, app_run_id])
        template_parameters = config_helpers.\
            get_template_parameters(self.config)
        template_parameters = \
            {k.upper(): v for k, v in template_parameters.items()}
        user_env = dict(os.environ,
                        NAMESPACE=self.namespace,
                        JOB_NAME=job_name,
                        IMAGE=remote_container_name,
                        **template_parameters)
        try:
            output = check_output(["make", "deploy"],
                                  env=user_env,
                                  stderr=STDOUT)
            print(output.decode("utf-8").strip())
            self._track_deployed_job(app_name, app_run_id)
        except CalledProcessError as e:
            print("Error while deploying app: {}".format(e.output))

    def _apply_template(self, out, filename, app_name, app_run_id):
        """take k8s-template data and create deployment in k8s dir
           job_sub_dir will be used in case of a mlt deploy -l to pass in the
           most current job being deployed to tail just in case there are > 1
           jobs that exist since mlt logs requires --job-name if > 1 job
        """
        self.job_sub_dir = self._track_deployed_job(app_name, app_run_id)
        with open(os.path.join(self.job_sub_dir, filename), 'w') as f:
            f.write(out)

        process_helpers.run(
            ["kubectl", "--namespace", self.namespace,
             "apply", "-R", "-f", self.job_sub_dir])

    def _track_deployed_job(self, app_name, app_run_id):
        """create a subdirectory in k8s with the deployed job name."""
        job_name = "-".join([app_name, app_run_id])
        return self.create_job_subdir(job_name)

    def create_job_subdir(self, job_name):
        """create a sub-directory in k8s with the given job name."""
        job_sub_dir = 'k8s/{}'.format(job_name)
        if not os.path.exists(job_sub_dir):
            os.makedirs(job_sub_dir)
        return job_sub_dir

    def _get_most_recent_podname(self):
        """don't know of a better way to do this; grab the pod
           created by the job we just deployed
           this gets the most recent pod by name, so we can exec
           into it once everything is done deploying
        """
        pods = self._get_pods_by_start_time()
        if pods:
            # we want last pod listed, podname is always first
            return pods[-1].split()[0]
        else:
            raise ValueError(
                "No pods found in namespace: {}".format(
                    self.namespace))

    def _get_pods_by_start_time(self):
        """helper func to return pods in current namespace by start time"""
        return process_helpers.run_popen(
            "kubectl get pods --namespace {} ".format(
                self.namespace) +
            "--sort-by=.status.startTime", shell=True
        ).stdout.read().decode('utf-8').strip().splitlines()

    def _patch_template_spec(self, data):
        """Makes `command` of template yaml `sleep infinity`.
           We will also add a `debug=true` label onto this pod for easy
           discovery later.
        """
        data = yaml.load(data)
        self.template_locations = []
        self.containers_locations = []

        self._find_metadata_and_container_spec(data)
        if not self.containers_locations:
            raise ValueError("Unable to find containers' in spec. Unable to "
                             "deploy interactively without these.")

        # TODO: confirm this, it appears that the yaml always makes
        # `containers:` a list of lists
        for location_list in self.containers_locations:
            for location in location_list:
                self._total_containers += 1
                # https://kubernetes.io/docs/tasks/inject-data-application/
                # define-command-argument-container/#notes
                # this will override both ENTRYPOINT and Cmd to ensure sleep
                # TODO: pick shell that exists in dockerfile
                # https://github.com/IntelAI/mlt/issues/348
                location.update({
                    'command': ["/bin/bash"],
                    'args': ["-c", "trap : TERM INT; sleep infinity & wait"]})
        if self.template_locations:
            for template in self.template_locations:
                template['metadata'] = {'labels': {'debug': 'true'}}
        return json.dumps(data)

    def _find_metadata_and_container_spec(self, data):
        """recursively finds `metadata` and `containers` location in
           deployment spec, that way we can apply debug label and update all
           container deployments to sleep
           data: current dict or list which we're parsing through
           original_spec: used to calculate the number of total containers
        """
        # containers and metadata will always be dicts, 98% sure
        data_is_dict = isinstance(data, dict)
        if data_is_dict:
            if 'template' in data:
                self.template_locations.append(data['template'])
                # we also can check for `replicas`, as these are at the same
                # level as `template`
                if 'replicas' in data and data['replicas'] != 1:
                    self._replicas_found = True
            if 'containers' in data:
                self.containers_locations.append(data['containers'])

        if data_is_dict:
            for key, val in data.items():
                self._find_metadata_and_container_spec(val)
        elif isinstance(data, list):
            for elem in data:
                self._find_metadata_and_container_spec(elem)

    def _exec_into_pod(self, podname):
        """wait til pod comes up and then exec into it"""
        print("Connecting to pod...")
        tries = 0
        while True:
            pod = process_helpers.run_popen(
                "kubectl get pods --namespace {} {} -o json".format(
                    self.namespace, podname),
                shell=True).stdout.read().decode('utf-8')
            if not pod:
                continue

            # check if pod is in running state
            # gcr stores an auth token which could be returned as part
            # of the pod json data
            pod = json.loads(pod)
            if pod.get('items') or pod.get('status'):
                # if there's more than 1 thing returned, we have
                # `pod['items']['status']` otherwise we will always have
                # `pod['status'], so by the second if below we're safe
                # first item is what we care about (or only item)
                if pod.get('items'):
                    pod = pod['items'][0]
                if pod['status']['phase'] == 'Running':
                    break

            if tries == self.args['--retries']:
                raise ValueError("Pod {} not Running".format(podname))
            tries += 1
            print("Retrying {}/{} \r".format(
                tries, self.args['--retries'])),
            time.sleep(1)

        # Get shell to the specified pod running in the user's namespace
        kubectl_exec = ["kubectl", "exec", "-it", podname,
                        "--namespace", self.namespace,
                        "--", "/bin/bash",
                        "-c", "cd /src/app; bash"]

        process_helpers.run_popen(kubectl_exec,
                                  stdout=None, stderr=None).wait()

    def _tail_logs(self):
        """need to tail the most recent job just in case there are more than
           one and a user runs `mlt deploy -l`
        """
        self.args["--job-name"] = self.job_sub_dir.replace('k8s/', '')
        log_helpers.call_logs(self.config, self.args)
