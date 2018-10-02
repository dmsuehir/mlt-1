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

import getpass
import json
import fnmatch
import os
import traceback
import yaml
from copy import deepcopy
from shutil import copy, copytree, copyfile, ignore_patterns
from subprocess import check_output
from termcolor import colored

from mlt.commands import Command
from mlt.utils import (config_helpers, constants, error_handling, git_helpers,
                       kubernetes_helpers, localhost_helpers, process_helpers)


class InitCommand(Command):
    def __init__(self, args):
        super(InitCommand, self).__init__(args)
        self.app_name = self.args["<name>"]
        self.template_name = self.args["--template"]

    def action(self):
        """Creates a new git repository based on an mlt template in the
           current working directory.
        """
        template_name = self.args["--template"]
        template_repo = self.args["--template-repo"]
        skip_crd_check = self.args["--skip-crd-check"]
        with git_helpers.clone_repo(template_repo) as temp_clone:
            templates_directory = os.path.join(
                temp_clone, constants.TEMPLATES_DIR, template_name)

            try:
                # The template configs get pulled into the mlt.json file, so
                # don't grab a copy of that in this app's directory
                copytree(templates_directory, self.app_name,
                         ignore=ignore_patterns(constants.TEMPLATE_CONFIG))

                # Get the template configs from the template and include them
                # when building the mlt json file
                param_file = os.path.join(templates_directory,
                                          constants.TEMPLATE_CONFIG)
                template_params = config_helpers.\
                    get_template_parameters_from_file(param_file)
                template_git_sha = git_helpers.get_latest_sha(os.path.join(
                    temp_clone, constants.TEMPLATES_DIR, template_name))
                if not skip_crd_check:
                    kubernetes_helpers.check_crds(app_name=self.app_name)

                if self.args["--enable-sync"]:
                    if localhost_helpers.binary_path('ksync'):
                        # Syncthing uses '.stignore' to ignore files during
                        # sync we also don't want to upload unneeded local data
                        app_ignore_file = os.path.join(self.app_name,
                                                       ".gitignore")
                        ksync_ignore_file = os.path.join(self.app_name,
                                                         ".stignore")
                        if self._check_update_yaml_for_sync():
                            copyfile(app_ignore_file, ksync_ignore_file)
                            with open(ksync_ignore_file, 'a+') as f:
                                f.write("\n.git/**")
                        else:
                            error_handling.throw_error(
                                "This app doesn't support syncing", 'yellow')
                    else:
                        error_handling.throw_error(
                            "ksync is not installed on localhost.", 'red')

                data = self._build_mlt_json(template_params, template_git_sha)

                # If the app has option for debugging failures, grab the
                # Kubernetes debug wrapper file and put it in the app directory
                if any(param["name"] == "debug_on_fail"
                       for param in template_params):
                    self._enable_debug_on_fail(temp_clone)

                with open(os.path.join(self.app_name,
                                       constants.MLT_CONFIG), 'w') as f:
                    json.dump(data, f, indent=2)

                self._init_git_repo()
            except OSError as exc:
                if exc.errno == 17:
                    error_msg = "Directory '{}' already exists: ".format(
                        self.app_name) + \
                        "delete before trying to initialize new application"
                    color = 'red'
                else:
                    error_msg = traceback.format_exc()
                    color = None
                error_handling.throw_error(error_msg, color)

    def _recursive_update_container_yaml(self, yaml_dict):
        if "containers" in yaml_dict:
            debug_on_fail_env = {'name': "DEBUG_ON_FAIL",
                                 'value': "$debug_on_fail"}
            for container in yaml_dict["containers"]:
                container["tty"] = True
                container["stdin"] = True
                if "env" in container:
                    if not any(e["name"] == "DEBUG_ON_FAIL" for e in
                               container["env"]):
                        container["env"].append(debug_on_fail_env)
                else:
                    container["env"] = [debug_on_fail_env]
        for k, v in yaml_dict.items():
            if isinstance(v, dict):
                v = self._recursive_update_container_yaml(v)
        return yaml_dict

    def _enable_debug_on_fail(self, temp_clone):
        # copy kubernetes debug wrapper file to the app
        copy(os.path.join(
            temp_clone, constants.DEBUG_WRAPPER_FILE),
            self.app_name)

        # update k8s yaml files
        k8s_dir = os.path.join(self.app_name, "k8s-templates")
        if os.path.isdir(k8s_dir):
            for k8s_file in os.listdir(k8s_dir):
                if os.path.splitext(k8s_file)[1] == ".yaml":
                    yaml_path = os.path.join(k8s_dir, k8s_file)
                    with open(yaml_path) as fh:
                        yaml_dict = yaml.load(fh)
                    updated_yaml = self._recursive_update_container_yaml(
                        yaml_dict)
                    with open(yaml_path, "w") as fh:
                        json.dump(updated_yaml, fh, indent=2)

    def _check_update_yaml_for_sync(self):
        # update k8s-template job spec, to keep the containers
        # running so that we can update code locally and have ksync
        # upload it to the running containers
        k8s_template_dir = os.path.join(self.app_name,
                                        "k8s-templates")
        if not os.path.exists(k8s_template_dir):
            return False

        k8s_template_specs = []
        for filename in os.listdir(k8s_template_dir):
            if fnmatch.fnmatch(filename, '*.yaml'):
                k8s_template_specs.append(os.path.join(
                    k8s_template_dir, filename))

        return_val_list = []
        for filename in k8s_template_specs:
            with open(filename, 'r+') as f:
                orig_filedata = f.readlines()
                # find matching begin and end commented sections for KSYNC and
                # exit with error if those sections are not properly matching
                begin_comment_indices = \
                    [i for i, x in enumerate(orig_filedata) if
                     "### BEGIN KSYNC SECTION" in x]
                end_comment_indices = \
                    [i for i, x in enumerate(orig_filedata) if
                     "### END KSYNC SECTION" in x]
                if len(begin_comment_indices) != len(end_comment_indices):
                    error_handling.throw_error(
                        "KSYNC comment section in file {} is "
                        "malformed".format(filename), 'red')

                final_filedata = deepcopy(orig_filedata)
                # using matched begin and end pairs for KSYNC comments, create
                # new lines to be written to the file
                for (begin, end) in zip(begin_comment_indices,
                                        end_comment_indices):
                    for k in range(begin, end + 1):
                        final_filedata[k] = orig_filedata[k].replace(
                            '#  ', '   ')
                        if final_filedata[k] != orig_filedata[k]:
                            return_val_list.append(True)

                if True in return_val_list[:-1]:
                    f.seek(0)
                    for line in final_filedata:
                        f.write(line)
                    f.truncate()

        return True in return_val_list

    def _build_mlt_json(self, template_parameters, template_git_sha):
        """generates the data to write to mlt.json"""
        data = {'name': self.app_name,
                'template_name': self.template_name,
                'namespace': self.app_name,
                'template_git_sha': template_git_sha
                }
        if not self.args["--registry"]:
            try:
                raw_project_bytes = check_output(
                    ["gcloud", "config", "list", "--format",
                     "value(core.project)"])
                project = raw_project_bytes.decode("utf-8").strip()
                data['registry'] = 'gcr.io/' + project
            except OSError as e:
                if "No such file or directory" in str(e):
                    # When the user did not provide a --registry, and gcloud
                    # was not found, warn them that they'll need to set a
                    # registry in the config.
                    print(colored("No registry name was provided and gcloud "
                                  "was not found.  Please set your container "
                                  "registry name in your mlt project using one"
                                  " of the following commands. \n\n"
                                  "For Google Container Registry:\n"
                                  "\tmlt template_config set registry "
                                  "<google_project_name>\n"
                                  "\nFor a Docker Registry:\n"
                                  "\tmlt template_config set registry "
                                  "<registry_name>\n", 'yellow'))
                else:
                    raise
        else:
            data['registry'] = self.args["--registry"]
        if not self.args["--namespace"]:
            data['namespace'] = getpass.getuser()
        else:
            data['namespace'] = self.args["--namespace"]

        # Add template specific parameters to the data dictionary
        if template_parameters:
            template_data = data[constants.TEMPLATE_PARAMETERS] = {}
            for param in template_parameters:
                template_data[param["name"]] = param["value"]

        return data

    def _init_git_repo(self):
        """
        Initialize new git repo in the project dir and commit initial state.
        """
        process_helpers.run(["git", "init", self.app_name])
        process_helpers.run(["git", "add", "."], cwd=self.app_name)
        print(process_helpers.run(
            ["git", "commit", "-m", "Initial commit."], cwd=self.app_name))
        if os.path.exists(os.path.join(self.app_name, ".stignore")):
            msg = "Once your application is built and deployed try the "\
                  "following mlt commands:\n"\
                  "{} - to setup syncing local changes to the running pods "\
                  "which in turn restarts the containers every time changes "\
                  "are made to local template code.\n"\
                  "This command only needs to run once.\n"\
                  "{} - to wake up the 'sync' agent after a local system "\
                  "reboot or long inactivity (default is 1 hour) or any other"\
                  " activity that causes 'sync' agent to die.\n"\
                  "{} - to teardown syncing setup and stop syncing local "\
                  "changes with remote pods.\n"\
                  "This command only need to run once.\n\n"\
                  "To ignore files and folders from syncing, add them to "\
                  "{} file."
            print(msg.format(colored("mlt sync create", attrs=['bold']),
                             colored("mlt sync reload", attrs=['bold']),
                             colored("mlt sync delete", attrs=['bold']),
                             colored(".stignore", attrs=['bold'])))
