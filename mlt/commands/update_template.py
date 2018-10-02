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
import random
import string
from subprocess import CalledProcessError
from mlt.commands import Command
from mlt.utils import (git_helpers, config_helpers,
                       error_handling, process_helpers)
from mlt.utils import constants
from distutils.dir_util import copy_tree


class UpdateTemplateCommand(Command):
    def __init__(self, args):
        super(UpdateTemplateCommand, self).__init__(args)
        self.config = config_helpers.load_config()
        self.template_repo = self.args["--template-repo"]

    def _get_backup_dir_name(self, app_name):
        random_string = ''.join(random.choice(
            string.ascii_uppercase + string.digits) for _ in range(6))
        return os.path.join(os.getcwd(),
                            os.pardir,
                            app_name + "_" + random_string + ".orig")

    def action(self):
        """Update the template instance with new template version
         if template is updated """

        if "template_name" not in self.config or \
                "template_git_sha" not in self.config:
            print("ERROR: mlt.json does not have either template_name "
                  "or template_git_sha. Template update is not possible.")
            return

        app_name = self.config["name"]
        template_name = self.config["template_name"]
        current_template_git_sha = self.config["template_git_sha"]

        orig_project_backup_dir = self._get_backup_dir_name(app_name)
        with git_helpers.clone_repo(self.template_repo) as temp_clone:
            application_dir = os.getcwd()
            clone_template_dir = os.path.join(temp_clone,
                                              constants.TEMPLATES_DIR,
                                              template_name)
            if not os.path.exists(clone_template_dir):
                print("Unable to update, template {} does "
                      "not exist in MLT git repo.".format(template_name))
                return

            latest_template_git_sha = \
                git_helpers.get_latest_sha(clone_template_dir)

            if current_template_git_sha == latest_template_git_sha:
                print("Template is up to date, no need for update.")
            else:
                print("Template is not up to date, updating template...")
                copy_tree(application_dir, orig_project_backup_dir)
                os.chdir(temp_clone)

                # create temp-branch using git sha from which template
                # was initiated and clean un-tracked files
                cmd = "git checkout -f {} -b temp-branch && git clean -f .". \
                    format(current_template_git_sha)
                process_helpers.run_popen(cmd, shell=True)

                # copy app dir content to temp clone template dir
                copy_tree(application_dir, clone_template_dir)

                # if there are any uncommitted changes to temp-branch,
                # commit them otherwise 'pull' from master will fail.
                output = process_helpers.run("git status".split(" "))
                if "Your branch is up-to-date" not in output:
                    process_helpers.run("git add --all ".split(" "))
                    commit_command = "git commit --message 'temp-commit'"
                    process_helpers.run(commit_command.split(" "))

                # merging latest template changes by pulling from master
                # into temp-branch
                try:
                    process_helpers.run("git pull origin master".split(" "),
                                        raise_on_failure=True)
                except CalledProcessError as e:
                    # When auto merge failed do not error out,
                    # let user review and fix conflicts
                    # for other errors exit
                    error_string = "Automatic merge failed; " \
                                   "fix conflicts and then commit the result"
                    if error_string not in e.output:
                        error_handling.throw_error(e.output)
                # copy content of clone template dir back to app dir
                copy_tree(clone_template_dir, application_dir)
                print("Latest template changes have merged using git, "
                      "please review changes for conflicts. ")
                print("Backup directory path: {}".format(
                    os.path.abspath(orig_project_backup_dir)))

                os.chdir(application_dir)
