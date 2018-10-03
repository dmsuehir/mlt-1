#!/usr/bin/env python
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


"""mlt.
Usage:
  mlt (-h | --help)
  mlt --version
  mlt init [--template=<template> --template-repo=<repo>]
      [--registry=<registry> --namespace=<namespace>]
      [--skip-crd-check] [--enable-sync] <name>
  mlt template_config (list | set <name> <value> | remove <name>)
  mlt build [--watch] [-v | --verbose]
  mlt deploy [--no-push] [-i | --interactive] [-l | --logs]
      [--retries=<retries>] [--skip-crd-check]
      [--since=<duration>] [-v | --verbose]
  mlt sync (create | reload | delete)
  mlt undeploy [--all] [--job-name=<name>]
  mlt status [--job-name=<name>] [-n <count> | --count <count>]
  mlt (template | templates) list [--template-repo=<repo>]
  mlt update-template [--template-repo=<repo>]
  mlt (log | logs) [--since=<duration>] [--retries=<retries>]
      [--job-name=<name>]
  mlt events [--job-name=<name>]

Options:
  --template=<template>     Template name for app
                            initialization [default: hello-world].
  --template-repo=<repo>    Git URL of template repository or the path to a
                            local MLT repository.
                            [default: https://github.com/IntelAI/mlt]
  --registry=<registry>     Container registry to use.
                            If none is set, will attempt to use gcloud.
  --namespace=<namespace>   Kubernetes Namespace to use.
                            If none is set, will attempt to create or
                            use a namespace identical to username.
  --skip-crd-check          To avoid crd check during mlt init
                            [default: False].
  --enable-sync             Without initializing templates with this option
                            'sync' and its subcommands 'create', 'reload' and
                            'delete' have no effect.
                            Use this option to initialize a template for
                            future sync capability.
                            'mlt sync create' should be called after user's
                            app is deployed to setup syncing local changes to
                            the running pods which in turn restarts the
                            containers every time changes are made to local
                            template code. This command only needs to run once.
                            'mlt sync reload' - to wake up the 'sync' agent
                            after a local system reboot or long inactivity
                            (default is 1 hour) or any other activity that
                            causes 'sync' agent to die.
                            'mlt sync delete' - to teardown syncing setup and
                            stop syncing local code changes with remote pods.
                            This command only need to run once.
                            To ignore files and folders from syncing, add them
                            to '.stignore' file.
                            [default: False].
  --watch                   Watch project directory and build on file changes
  --verbose                 Prints build or deploy logs
  --no-push                 Deploy your project to kubernetes using the same
                            image from your last run.
  --interactive             Rewrites all container commands to infinite sleep,
                            and then drops user into `kubectl exec` shell if
                            there's only one container deployed. Otherwise,
                            outputs helpful text to help you connect to
                            your running container.
                            Adds a `debug=true` label for easy discovery later.
  --retries=<retries>       Number of times to retry while waiting for pods to
                            be running. Waits 1 second between retrying. Used
                            with interactive deploy and logs.
                            [default: 120]
  --since=<duration>        Returns logs newer than a relative
                            duration like 10s, 1m, or 2h [default: 1m].
  --logs                    Tail logs after deploying [default: False]
  --all                     Undeploy all of the deployed jobs.
  --job-name=<name>         Job name to undeploy.
  --count=<count>           Number of job statuses to return in `mlt status`
                            [default: 5]
"""

# Note that new commands/flags should be documented in docs/features.md

import os
import sys
from docopt import docopt

import mlt
from mlt.commands import (BuildCommand, TemplateConfigCommand, DeployCommand,
                          EventsCommand, InitCommand, LogsCommand,
                          StatusCommand, SyncCommand, TemplatesCommand,
                          UndeployCommand, UpdateTemplateCommand)
from mlt.utils import regex_checks


# every available command and its corresponding action will go here
COMMAND_MAP = (
    ('build', BuildCommand),
    ('template_config', TemplateConfigCommand),
    ('deploy', DeployCommand),
    ('init', InitCommand),
    ('status', StatusCommand),
    ('sync', SyncCommand),
    ('template', TemplatesCommand),
    ('templates', TemplatesCommand),
    ('update-template', UpdateTemplateCommand),
    ('undeploy', UndeployCommand),
    ('log', LogsCommand),
    ('logs', LogsCommand),
    ('events', EventsCommand)
)


def run_command(args):
    """maps params from docopt into mlt commands"""
    for command, CommandClass in COMMAND_MAP:
        if args[command]:
            CommandClass(args).action()
            return


def sanitize_input(args, regex=None):
    """Ensures that the values passed to us via flags aren't malicious
       Or attempts to at least! Also sets types of vars and other tweaks
       Optional regex: Match the input based on the regex too
                       Raise ValueError if no match
       TODO: this can definitely be smarter...see if docopt can do some of it
       This could also be leveraged: https://github.com/keleshev/schema
       It is recommended on docopt github to do validation

       Also sources dev config from either `mlt.conf` or conf file provided
    """
    # docker requires repo name to be in lowercase
    if args["<name>"] and args.get("init"):
        args["<name>"] = args["<name>"].lower()

        if not regex_checks.k8s_name_is_valid(args["<name>"], "pod"):
            raise ValueError("Name {} not valid.\nName must comply with the "
                             "Kubernetes naming restrictions, which means that"
                             " it must consist of lowercase alphanumeric "
                             "characters or '-' and must start and end with "
                             "an alphanumeric character.".
                             format(args["<name>"]))

    # we only do logic on full flag name rather than alias
    if args["-i"]:
        args["--interactive"] = True
    if args["-l"]:
        args["--logs"] = True
    if args["-v"]:
        args["--verbose"] = True
    if args["-n"]:
        args["--count"] = True

    # docopt doesn't support type assignment:
    # https://github.com/docopt/docopt/issues/8
    args['--retries'] = int(args['--retries'])
    if args['<count>']:
        args['<count>'] = int(args['<count>'])

    # verify that the specified namespace is valid
    if args['--namespace'] and not regex_checks.k8s_name_is_valid(
            args['--namespace'], "namespace"):
        raise ValueError("Namespace {} not valid. See "
                         "https://kubernetes.io/docs/concepts/overview"
                         "/working-with-objects/names/#names"
                         .format(args['--namespace']))

    # Set and Unset config commands require the name arg
    if (args.get('set') or args.get('remove')) and not args.get('<name>'):
        raise ValueError("Name of the configuration parameter must be "
                         "specified.")

    return args


def load_config(args):
    """Loads env vars to be used as defaults for various flags
       See features.md for format required
    """
    for env_var, val in os.environ.items():
        if env_var.startswith('MLT'):
            env_var = env_var.lower().replace('_', '-')[4:]
            # don't override what a user sets on command line
            if not args.get(env_var):
                # convert to bool if possible
                if val.lower() in ('true', 'false'):
                    val = val.lower() == 'true'
                args[env_var] = val
    return args


def main():
    try:
        args = load_config(sanitize_input(
            docopt(__doc__, version="ML Container Templates Version {}".
                   format(mlt.__version__))))
        run_command(args)
    # we want to allow SystemExit as we're intentionally catching those
    # via the error_handling module
    except Exception:
        print("You've discovered a bug! Please make an issue on "
              "https://github.com/IntelAI/mlt/issues if one does not "
              "exist already.\nMLT command: {}\n".format(" ".join(sys.argv)))
        raise
