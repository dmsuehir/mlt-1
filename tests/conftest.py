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

import inspect
import os
import pytest
import shutil
import sys
import tempfile
from mock import MagicMock
from subprocess import Popen
from threading import Timer

# enable test_utils to be used in tests via `from test_utils... import ...
sys.path.append(os.path.join(os.path.dirname(__file__), 'test_utils'))

MODULES = ('mlt.tests',)
MODULES_REPLACE = ('tests.unit', 'mlt')


def patch_setattr(module_names, module_replace, monkeypatch, path, m):
    """ Credit for this goes mostly to @megawidget
    do not call this directly -- assumes the fixture's caller is two stacks up
    and will correspondingly guess the module path to patch
    `path` can be:
        1. an object, if it's defined in the module you're testing
        2. a name, if it's imported in the module you're testing
        3. a full path a la traditional monkeypatch
    """
    if hasattr(path, '__module__'):
        monkeypatch.setattr('.'.join((path.__module__, path.__name__)), m)
        return
    elif any(path.startswith(i + '.') for i in module_names):
        # full path.  OK.
        monkeypatch.setattr(path, m)
    else:
        # assume we're patching stuff in the file the test file is supposed to
        # be testing
        fn = inspect.getouterframes(inspect.currentframe())[2][1]
        fn = os.path.splitext(os.path.relpath(fn))[0]
        module = fn.replace(os.path.sep, '.').replace('test_', '').replace(
            *module_replace)
        try:
            monkeypatch.setattr('.'.join((module, path)), m)
        except AttributeError:
            # handle mocking builtins like `open`
            if sys.version_info.major == 3:
                builtin = 'builtins'
            else:
                builtin = '__builtin__'
            # NOTE: `path` should be just the builtin, like `open`
            # usage: patch('open')
            monkeypatch.setattr("{}.{}".format(builtin, path), m)


@pytest.fixture
def patch(monkeypatch):
    """allows us to add easy autouse fixtures by patching anything we want
       Usage: return something like this in a @pytest.fixture
       - patch('files.fetch_action_arg', MagicMock(return_value='output'))
       Without the second arg, will default to just MagicMock()
    """

    def wrapper(path, mock=None):
        m = mock if mock is not None else MagicMock()
        patch_setattr(MODULES, MODULES_REPLACE, monkeypatch, path, m)
        return m

    return wrapper


# each test that calls `mlt init` will create app dir inside of this temp dir
def pytest_sessionstart(session):
    pytest.workdir = tempfile.mkdtemp()


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(pytest.workdir)


# SECTION TO GRAB MORE LOGS IF TEST FAILS

# from https://docs.pytest.org/en/latest/example/simple.html
#     #making-test-result-information-available-in-fixtures
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # set a report attribute for each phase of a call, which can
    # be "setup", "call", "teardown"

    setattr(item, "rep_" + rep.when, rep)


@pytest.fixture(autouse=True)
def dump_extra_debug_info(request):
    yield
    # request.node is an "item" because we use the default
    # "function" scope
    if request.node.rep_setup.passed and request.node.rep_call.failed:
        py_version = sys.version_info.major

        # clone and build mlt at `master` if not done already
        # if 2 threads execute this at once it'll be okay because `os.system`
        # will error silently
        mlt_path = '/tmp/mltAtMaster'
        if not os.path.exists(mlt_path):
            os.system(
                """echo "Building MLT at master for debugging" &&
                    git clone git@github.com:NervanaSystems/mlt.git \
                      /tmp/mltAtMaster &&
                   pushd /tmp/mltAtMaster &&
                   PY={} make venv &&
                   popd
                """.format(py_version))
        print('DEBUG INFO')

        venv_name = '.venv' if py_version == 2 else '.venv3'
        mlt_cmd = os.path.join(mlt_path, venv_name, 'bin', 'mlt')

        def run_cmd(sub_cmd):
            """Runs various mlt commands and dumps output"""
            exec_cmd = "echo 'Running mlt {}...' && pushd {} > /dev/null" + \
                " 2>&1 && {} {} && echo '' && popd > /dev/null 2>&1"
            proc = Popen(exec_cmd.format(
                sub_cmd, pytest.project_dir, mlt_cmd, sub_cmd),
                stdout=True, stderr=True, shell=True)
            # no cmd should take over 5 sec to run
            # if logs does, kill after 5 sec as there's no logs then
            timer = Timer(5, lambda x: x.kill(), [proc])
            out = err = ''
            try:
                timer.start()
                out, err = proc.communicate()
            finally:
                timer.cancel()

            if out:
                print(out)
            if err:
                print(err)

        run_cmd("events")
        run_cmd("logs")
        run_cmd("status")

# END SECTION TO GRAB MORE LOGS IF TEST FAILS
