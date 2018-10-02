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
import pytest
import shutil
import signal
import time
import uuid
from termcolor import colored
from subprocess import PIPE

from mlt.utils.files import get_deployed_jobs, get_truncated_job_name
from mlt.utils.git_helpers import clone_repo, get_experiments_version
from mlt.utils.process_helpers import run, run_popen
from project import basedir


class CommandTester(object):

    @pytest.fixture(scope='class', autouse=True)
    def setup(self):
        # workaround for issue described here:
        # https://github.com/pytest-dev/pytest/issues/3778
            # issuecomment-411899446
        # this will enable us to use pytest 3.7.1

        # just in case tests fail, want a clean namespace always
        type(self).registry = os.getenv('MLT_REGISTRY', 'localhost:5000')

        # ANY NEW TFJOBS NEED TO HAVE THEIR TEMPLATE NAMES LISTED HERE
        # TFJob terminates pods after completion so can't check old pods
        # for status of job completion
        type(self).tfjob_templates = ('tf-dist-mnist', 'tf-distributed')

    def _set_new_mlt_project_vars(self, template):
        """init calls this function to reset a new project's test vars"""
        # putting an `a` here because PytorchJob requires a letter in front
        # it tries to create a service based on image name
        # using template name to better id the job that's running for debugging
        self.app_name = 'a' + template[:4] + str(uuid.uuid4())[:4]
        self.namespace = getpass.getuser() + '-' + self.app_name
        # useful debug print to id which test is running when
        print("Running test with namespace {}".format(self.namespace))

        self.project_dir = os.path.join(pytest.workdir, self.app_name)
        self.mlt_json = os.path.join(self.project_dir, 'mlt.json')
        self.build_json = os.path.join(self.project_dir, '.build.json')
        self.deploy_json = os.path.join(self.project_dir, '.push.json')
        self.train_file = os.path.join(self.project_dir, 'main.py')

    def _grab_latest_pod_or_tfjob(self):
        """grabs latest pod by startTime"""
        if self.template in self.tfjob_templates:
            # NOTE: do we need some sort of time filter here too?
            obj_string = "kubectl get tfjob -a --namespace {} -o json".format(
                self.namespace)
        else:
            obj_string = "kubectl get pods -a --namespace {}".format(
                self.namespace) + " --sort-by=.status.startTime -o json"
        objs, _ = self._launch_popen_call(obj_string, shell=True,
                                          return_output=True)
        if objs:
            # tfjob is special and puts the `Succeeded` status on the `state`
            # rather than the `phase` like everything else
            # it also orders its jobs latest-first, so we actually want
            # the first job
            if "tfjob" in obj_string:
                return json.loads(objs).get('items')[0]['status']["state"]
            else:
                return json.loads(objs).get('items')[-1]['status']["phase"]
        else:
            raise ValueError("No pod(s) deployed to namespace {}".format(
                self.namespace))

    def _grab_job_name(self):
        """used with use_job_name flag to get the first of the list of the
           deployed jobs
        """
        return get_deployed_jobs(
            job_names_only=True, work_dir=self.project_dir)[0]

    def _setup_experiments_sa(self):
        """
        Running the experiments template requires role/rolebindings setup
        for the namespace.  This method will create the namespace, and then
        set the roles/rolebindings that we get from the experiments repo.
        """
        experiments_repo = "https://github.com/IntelAI/experiments.git"
        with clone_repo(experiments_repo) as temp_clone:
            # get known version of experiments repo
            command = ['git', 'checkout', get_experiments_version()]
            self._launch_popen_call(command, cwd=temp_clone)

            # get the sa.yaml file and then replace 'demo' with our namespace
            example_dir = os.path.join(temp_clone, "examples/demo")
            with open(os.path.join(example_dir, "sa.yaml"), 'r') as sa_file:
                sa_yaml = sa_file.read()
            sa_yaml = sa_yaml.replace("demo", self.namespace)

            # write the yaml with the test namespace out to a new file
            new_sa_file = os.path.join(temp_clone, example_dir,
                                       "sa_{}.yaml".format(self.namespace))
            with open(new_sa_file, 'w') as sa_file:
                sa_file.write(sa_yaml)

            # create namespace so that we can add roles
            command = ['kubectl', 'create', 'ns', self.namespace]
            self._launch_popen_call(command, stderr_is_not_okay=True)

            # create roles/rolebindings using kubectl command
            command = ['kubectl', 'create', '-f', new_sa_file]
            self._launch_popen_call(command, stderr_is_not_okay=True)

    def init(self, template='hello-world', template_repo=basedir(),
             enable_sync=False, existing_app_dir=None):
        self._set_new_mlt_project_vars(template)

        # If there isn't an existing app, run mlt init to create a new one
        if not existing_app_dir:
            init_options = ['mlt', 'init',
                            '--registry={}'.format(self.registry),
                            '--template-repo={}'.format(template_repo),
                            '--namespace={}'.format(self.namespace),
                            '--template={}'.format(template), self.app_name]
            if enable_sync:
                init_options.append('--enable-sync')
            self._launch_popen_call(init_options, cwd=pytest.workdir)
        else:
            shutil.copytree(existing_app_dir, self.project_dir)
            self.config("set", "namespace", self.namespace)
            self.config("set", "name", self.app_name)
            self.config("set", "registry", self.registry)

        # keep track of template we created so we can check if it's a TFJob
        # that terminates pods after completion so we need to check the crd
        # for status on if job was successful
        self.template = template
        assert os.path.isfile(self.mlt_json)
        with open(self.mlt_json) as f:
            standard_configs = {
                'namespace': self.namespace,
                'name': self.app_name,
                'registry': self.registry
            }
            actual_configs = json.loads((f.read()))
            assert dict(actual_configs, **standard_configs) == actual_configs

        if not existing_app_dir:
            # verify we created a git repo with our project init
            assert "On branch master" in run(
                "git --git-dir={}/.git --work-tree={} status".format(
                    self.project_dir, self.project_dir).split())

        # setup additional namespace configs for experiments
        if template == 'experiments':
            self._setup_experiments_sa()

    def config(self, subcommand="list", config_name=None, config_value=None):
        command = ['mlt', 'template_config', subcommand]

        if config_name:
            command.append(config_name)

        if config_value:
            command.append(config_value)

        output, err = self._launch_popen_call(
            command, return_output=True, stderr_is_not_okay=True)

        if subcommand == "list":
            assert output

        return output, err

    def build(self, watch=False, verbose=False):
        build_cmd = ['mlt', 'build']
        call_args = {'command': build_cmd}

        if verbose:
            build_cmd.append('--verbose')
            call_args['return_output'] = True
            call_args['stderr_is_not_okay'] = True

        if watch:
            build_cmd.append('--watch')
            # we don't want to wait for the popen call to finish
            # because it'll go until we kill it
            call_args['wait'] = True

            build_proc = self._launch_popen_call(**call_args)
            # ensure that `mlt build --watch` has started
            time.sleep(3)
            # we need to simulate our training file changing
            self._launch_popen_call("echo \"print('hello')\" >> {}".format(
                self.train_file), shell=True)
            # wait for 6 mins (for timeout) or until we've built our image
            # then kill the build proc or it won't terminate
            # we could be building TF which takes awhile
            start = time.time()
            while not os.path.exists(self.build_json):
                time.sleep(1)
                if time.time() - start >= 360:
                    break
            build_proc.kill()
        else:
            # verbose displays normal docker output rather than progressbar
            if verbose:
                out, _ = self._launch_popen_call(**call_args)
                assert "Sending build context to Docker daemon" in out, out
            else:
                self._launch_popen_call(**call_args)

        assert os.path.isfile(self.build_json)
        with open(self.build_json) as f:
            build_data = json.loads(f.read())
            assert 'last_container' in build_data and \
                   'last_build_duration' in build_data
            # verify that we created a docker image
            self._launch_popen_call(
                "docker image inspect {}".format(build_data['last_container']),
                shell=True, stdout=None, stderr=None)

    def deploy(self, no_push=False, interactive=False, retries=10,
               sync=False, logs=False, verbose=False):
        deploy_cmd = ['mlt', 'deploy', '--retries', str(retries)]
        call_args = {'command': deploy_cmd}
        if no_push:
            deploy_cmd.append('--no-push')
        if interactive:
            deploy_cmd.append('--interactive')
        if verbose:
            deploy_cmd.append('--verbose')
            call_args['return_output'] = True
        if logs:
            # make log command string so we can shell it out due to ">"
            log_file = '/tmp/logFile{}'.format(self.app_name)
            deploy_cmd = " ".join(deploy_cmd) + \
                         ' --logs > {}'.format(log_file)
            # we want to kill all procs generated from our group
            # includes subprocs of subprocs (mlt deploy --> kubetail)
            p = self._launch_popen_call(
                deploy_cmd, wait=True, shell=True, stdout=True,
                stderr=True, preexec_fn=os.setpgrp)

            # try for 10 min to check if log file has been written to yet
            for check in range(600):
                # don't delete the log file after test runs in case dev needs
                # to debug why test fails
                try:
                    output = ''
                    with open(log_file, "r") as f:
                        output = f.read()
                    """verify log output as `mlt deploy --logs` chains
                       subprocess calls and we don't track pid so we can't
                       access sub-subproc log output via piping output to
                       other proc
                    """
                    assert "Will tail" in output
                    assert self.app_name in output
                    break
                except (AssertionError, IOError):
                    # ignore if file doesn't exist yet (model not deployed yet)
                    # also ignore if file created but not written to yet
                    pass
                time.sleep(1)
            else:
                raise ValueError("No log output found.")

            # kill `mlt deploy`'s `kubetail` call (subprocess of subprocess)
            os.killpg(os.getpgid(p.pid), signal.SIGINT)
            return
        else:
            # verbose displays regular docker output instead of progressar
            if verbose:
                out, _ = self._launch_popen_call(**call_args)
                assert "The push refers to" in out, out
            else:
                self._launch_popen_call(**call_args)

        if not no_push:
            assert os.path.isfile(self.deploy_json)
            with open(self.deploy_json) as f:
                deploy_data = json.loads(f.read())
                assert 'last_push_duration' in deploy_data and \
                       'last_remote_container' in deploy_data

    def sync(self, create=False, reload=False, delete=False):
        sync_cmd = ['mlt', 'sync']
        if create:
            sync_cmd.append('create')
        if reload:
            sync_cmd.append('reload')
        if delete:
            sync_cmd.append('delete')
        self._launch_popen_call(sync_cmd)

    def status(self, count=1, job_statuses=True):
        """
           count: number of jobs to show status for
           job_statuses: assert 0 job statuses in output (for undeploy check)
        """
        output, _ = self._launch_popen_call(
            ['mlt', 'status', '-n', str(count)], return_output=True,
            stderr_is_not_okay=True)

        if job_statuses:
            assert output.count('Job: ') == count, [output, self.project_dir]
            assert output.count('Creation Time: ') == count, output
        else:
            assert output == ''
        return output

    def logs(self, use_job_name=False):
        command = ['mlt', 'logs']
        if use_job_name:
            command.append("--job-name={}".format(self._grab_job_name()))

        # If 'mlt logs' succeed next call won't error out
        p = self._launch_popen_call(command, wait=True)

        # kill the 'mlt logs' process
        p.send_signal(signal.SIGINT)

    def events(self, use_job_name=False):
        """We will check for if there's a message with `Created pod: ...`
           in the events, and that it was successful
        """
        command = ['mlt', 'events']
        if use_job_name:
            command.append("--job-name={}".format(self._grab_job_name()))

        output, _ = self._launch_popen_call(
            command, return_output=True, stderr_is_not_okay=True)

        job_name = get_truncated_job_name(self._grab_job_name())
        # horovod doesn't have pod creation in events because of custom deploy
        if 'ahoro' not in self.app_name:
            assert "Created pod: {}".format(job_name) in output
            assert "SuccessfulCreate" in output
        else:
            assert job_name in output

    def undeploy(self, all_jobs=False, use_job_name=None):
        command = ['mlt', 'undeploy']
        if all_jobs:
            command.append("--all")
        elif use_job_name:
            command.append("--job-name={}".format(self._grab_job_name()))
        self._launch_popen_call(command)

    # TODO: merge with undeploy(...) to use undeploy(all_jobs=True)
    # in teardown()
    def undeploy_for_test_teardown(self):
        """use `mlt undeploy --all` in test teardown."""
        command = ['mlt', 'undeploy', '--all']
        # expected output message in case of second undeploy
        expected_out = "This app has not been deployed yet."
        self._launch_popen_call(command, allow_err=True,
                                expected_err_msg=expected_out)
        # verify no more deployment job
        # TODO: this will always return a 0 exit code...
        self._launch_popen_call(
            "kubectl get jobs --namespace={}".format(
                self.namespace), shell=True)

    def update_template(self, template_repo=basedir()):
        update_cmd = ['mlt', 'update-template']
        if template_repo:
            update_cmd.append("--template-repo={}".format(template_repo))
        output, err = self._launch_popen_call(
            update_cmd, return_output=True, stderr_is_not_okay=True)

        # verify that we have some output
        assert output
        return output.decode("utf-8")

    def _launch_popen_call(self, command, cwd=None, return_output=False,
                           shell=False, stdout=PIPE, stderr=PIPE,
                           stderr_is_not_okay=False, wait=False,
                           preexec_fn=None, allow_err=False,
                           expected_err_msg=None):
        """Lightweight wrapper that launches run_popen and handles dumping
           output if there was an error
           cwd: where to launch popen call from
           return_output: whether to return the process itself or the output
                          and error instead. Need 2 options for things like
                          `--watch` flag, where we kill the proc later
           shell: whether to shell out the popen call, NOTE: if True,
                  the command needs to be a string. This is helpful for things
                  like `|` in the command.
           stderr_is_not_okay: some commands like `git checkout` or progressbar
                           dump their output to stderr so we need to allow it
                           THEORY: stderr is unbuffered so dynamic progressbars
                           might want to dump to stderr. This is for those
                           commands that actually don't want any stderr.
           wait: for the build watch command, we don't want to call `.wait()`
                    on it because we need to check when we edit watched file
           preexec_fn: runs a func after the fork() call but before exec()
                       to run the shell. Useful for killing subprocesses of
                       subprocesses (like `mlt deploy -l` --> `kubetail`)
           allow_err: if True, we expect the command to fail and want to
                      test with an expected error message
                      `expected_err_msg`.
           expected_err_msg: the expected error message if the command
                             execution fails, it's used when `allow_err`
                             is True.
        """
        if cwd is None:
            # default to project dir if that's defined, otherwise just use /tmp
            cwd = getattr(self, 'project_dir', '/tmp')
        p = run_popen(command, stdout=stdout,
                      stderr=stderr, shell=shell, cwd=cwd,
                      preexec_fn=preexec_fn)
        if not wait:
            out, err = p.communicate()

            error_msg = "Popen call failed:\nSTDOUT:{}\n\nSTDERR:{}".format(
                str(out), colored(str(err), 'red'))
            if allow_err and p.wait() != 0:
                output = out.decode("utf-8").strip()
                assert output == expected_err_msg, error_msg
            else:
                assert p.wait() == 0, error_msg

            if stderr_is_not_okay is True:
                assert not err, error_msg

            if return_output:
                out = out.decode('utf-8').strip()
                return out, err
            else:
                return p
        else:
            return p

    def verify_pod_status(self, expected_status="Succeeded"):
        """verify that our latest job did indeed get deployed to k8s and
         gets to the specified status"""
        # TODO: probably refactor this function
        # allow for 3 min for the pod to start creating;
        # pytorch operator causes pods to fail for a bit before success
        # which is out of our hands
        start = time.time()
        pod_status = None
        while pod_status is None:
            try:
                pod_status = self._grab_latest_pod_or_tfjob()
            # there are so many different kinds of errors if pods aren't
            # ready yet that we'll ignore all of them
            except:  # noqa
                # if no pod is available, or pods is an empty dict, ignore
                # for 2 mins
                # OSError is to handle this:
                # `couldn't find any field with path "{.status.startTime}"
                # in the list of objects``
                # if there are no pods yet
                time.sleep(1)
                if time.time() - start >= 180:
                    break

        # wait for pod to finish, up to 5 min for pending and 5 for running
        # not counting interactive that will always be running
        start = time.time()
        while pod_status == "Pending":
            time.sleep(1)
            pod_status = self._grab_latest_pod_or_tfjob()
            if time.time() - start >= 300:
                break

        if expected_status != pod_status:
            # since new pods could come up, we might find another 'Pending' pod
            while pod_status == "Running" or pod_status == "Pending":
                if pod_status == expected_status:
                    break
                time.sleep(1)
                pod_status = self._grab_latest_pod_or_tfjob()
                if time.time() - start >= 600:
                    break

            assert pod_status == expected_status, \
                "Expected pod status '{}' but was '{}'".\
                format(expected_status, pod_status)
