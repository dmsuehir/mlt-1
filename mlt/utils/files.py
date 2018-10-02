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
import glob
import json
import os
import yaml

from mlt.utils import error_handling

# to support python2 as well
try:
    FileNotFoundError
except NameError:
    FileNotFoundError = OSError


def fetch_action_arg(action, arg):
    """fetches data from command json files"""
    action_json = '.{}.json'.format(action)
    if os.path.isfile(action_json):
        with open(action_json) as f:
            return json.load(f).get(arg)


def is_custom(target):
    """a job is custom if there's a Makefile in the top level dir
       and the Makefile has the `target` rule inside of it
    """
    custom = False
    if os.path.isfile('Makefile'):
        with open('Makefile') as f:
            for line in f:
                if line.startswith(target):
                    custom = True
                    break
    return custom


def get_deployed_jobs(job_names_only=False, work_dir=None):
    """get the list of the deployed jobs sorted by creation time

       job_names_only: strips the `k8s` folder from the job name and only
                       returns the job name with no folder path
       work_dir:       the working directory to use to make the `glob` call in
                       if different than the cwork_dir
    """
    # if work_dir not passed in we want `k8s`, else `folder_passed_in` + `k8s`
    work_dir = 'k8s' if not work_dir else os.path.join(work_dir, 'k8s')
    jobs = glob.glob(os.path.join(work_dir, '*'))
    jobs.sort(key=lambda x: os.path.getmtime(x))
    if job_names_only:
        jobs = [os.path.basename(job) for job in jobs]
    return jobs


def _get_truncated_job_name(job_name):
    """When we need to truncate the job name (which is the MLT app name plus
       the app run id) in order to get the prefix for pod names.

        Pod names have max len of 253 so shorten all jobs returned by
        truncating after the last `-` of the app run id and then shortening.
        We do a fuzzy search anyhow so shortening to max 200 chars is plenty.
    """
    return job_name[:job_name.rfind("-")][-53:]


def get_only_one_job(job_desired, error_msg):
    """Checks if job desired is in the list of jobs available
       Throws error if more than 1 job found or job doesn't exist
       Function assumes error handling of if jobs exist happens elsewhere
       TODO: This could be more efficient

       If there are no jobs deployed or job desired not found,
       we'll print an error message and exit. print + exit(1) is nicer for
       the user than a traceback via ValueError so we'll go with the former

       job_desired: `--job-name` parameter string passed to us
       error_msg: What to print if > 1 job or job not found
    """
    jobs = get_deployed_jobs(job_names_only=True)
    # too many jobs exist with no --job-name flag
    if len(jobs) > 1 and not job_desired:
        error_handling.throw_error('{}\nJobs to choose from are:\n{}'.format(
            error_msg, '\n'.join(jobs)))
    elif job_desired:
        # --job-name was passed in to us
        if job_desired in jobs:
            return _get_truncated_job_name(job_desired)
        else:
            error_handling.throw_error(
                "Job {} not found.\nJobs to choose from are:\n{}".format(
                    job_desired, '\n'.join(jobs)))
    elif jobs:
        # no --job-name flag passed and only 1 job exists
        return _get_truncated_job_name(jobs[0])
    else:
        error_handling.throw_error("No jobs are deployed.")


def get_job_kinds():
    """returns `kind: ` from K8s yaml files if possible as a set obj
       also returns whether or not all deployment kinds are the same
       NOTE: need to be in an mlt project dir
    """
    kinds = set()
    try:
        for yaml_file in os.listdir('k8s-templates'):
            with open(os.path.join('k8s-templates', yaml_file), "r") as f:
                data = yaml.load_all(f)
                for template in data:
                    kinds.add(template['kind'].lower())
    except FileNotFoundError:
        return None, False

    return kinds, len(kinds) == 1
