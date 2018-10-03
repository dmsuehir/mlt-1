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
import pytest
from mock import MagicMock, patch

from mlt.main import main, run_command

from test_utils.io import catch_stdout

"""
All these tests assert that given a command arg from docopt we call
the right command
"""


@pytest.fixture
def docopt_mock(patch):
    return patch('docopt')


@pytest.fixture
def run_command_mock(patch):
    return patch('run_command')


@pytest.mark.parametrize('command',
                         ['build', 'deploy', 'init', 'template', 'templates',
                          'undeploy', 'foo'])
def test_run_command(command):
    # couldn't get this to work as a function decorator
    with patch('mlt.main.COMMAND_MAP', ((command, MagicMock()),)) \
            as COMMAND_MAP:
        run_command({command: True})
        COMMAND_MAP[0][1].return_value.action.assert_called_once()


@pytest.mark.parametrize('args', [
    {'<name>': 'Capitalized-Name',
     '-i': False, '-l': False, '-v': False, '--retries': '5',
     '--job-name': None, '-n': True, "<count>": 10},
    {'-i': True, '-l': False, '-v': False, '<name>': 'foo', '--retries': '5',
     '--job-name': 'app', '-n': True, "<count>": 10},
    {'-i': True, '-l': False, '-v': False, '<name>': 'foo',
        '--retries': '8', '--job-name': None, '-n': True, "<count>": 10},
    {'-i': True, '-l': False, '-v': True, '<name>': 'foo', '--retries': '8',
     '--job-name': 'app', '-n': True, "<count>": 10}])
def test_main_various_args(run_command_mock, docopt_mock, args):
    docopt_mock.return_value = args
    # add common args and expected arg manipulations
    args['--namespace'] = 'foo'
    args['--retries'] = int(args['--retries'])
    args['--interactive'] = True
    args['<name>'] = args['<name>']
    main()
    run_command_mock.assert_called_with(args)


def test_main_invalid_names(docopt_mock):
    """ Test that an invalid name throws a ValueError """
    args = {
        # underscore should not be allowed in name for the init command
        "init": True,
        "<name>": "foo_bar"
    }
    docopt_mock.return_value = args
    with pytest.raises(ValueError):
        main()


def test_main_invalid_namespace(docopt_mock):
    """ Test that an invalid namespace throws a ValueError """
    args = {
        "<name>": "foo",
        "<count>": 3,
        # underscore should not be allowed in namespace
        "--namespace": "foo_bar",
        "-i": False,
        "-l": False,
        "-v": False,
        "-n": True,
        "--retries": 5
    }
    docopt_mock.return_value = args
    with pytest.raises(ValueError):
        main()


@pytest.mark.parametrize("command", [
    "set",
    "remove"
])
def test_main_set_remove_name(docopt_mock, command):
    """ Ensure that set and unset commands require name arg."""
    args = {
        command: True,
        "--namespace": "foo",
        "<name>": "",
        "<count>": 10,
        "-i": False,
        "-l": False,
        "-v": False,
        "-n": True,
        "--retries": 5
    }
    docopt_mock.return_value = args
    with pytest.raises(ValueError):
        main()


def test_main_load_args(docopt_mock, run_command_mock):
    """Set env var and verify that it's loaded in the args"""
    args = {
        "--namespace": "foo",
        "<name>": "bar",
        "<count>": 1,
        "-i": False,
        "-l": False,
        "-v": False,
        "-n": True,
        "--retries": 5,
        "status": True
    }
    docopt_mock.return_value = args
    os.environ["MLT_REGISTRY"] = "gcr.io/foobar"
    os.environ["MLT_SKIP_CRD_CHECK"] = "True"
    main()
    # can't check `.items() <= .items()` here because of python2
    assert args["registry"] == "gcr.io/foobar", args["registry"]
    assert args["skip-crd-check"] is True, args["skip-crd-check"]


def test_main_uncaught_exception(docopt_mock, run_command_mock):
    """tests what happens when some part of the program fails"""
    run_command_mock.side_effect = Exception
    with catch_stdout() as output:
        with pytest.raises(Exception):
            main()
        output = output.getvalue()
        assert "You've discovered a bug! Please make an issue on " + \
            "https://github.com/IntelAI/mlt/issues if one does not " + \
            "exist already." in output, output
