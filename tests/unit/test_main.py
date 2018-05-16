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

import pytest
from mock import MagicMock, patch

from mlt.main import main, run_command

"""
All these tests assert that given a command arg from docopt we call
the right command
"""


@pytest.mark.parametrize('command',
                         ['build', 'deploy', 'init', 'template', 'templates',
                          'undeploy', 'foo'])
def test_run_command(command):
    # couldn't get this to work as a function decorator
    with patch('mlt.main.COMMAND_MAP', ((command, MagicMock()),)) \
            as COMMAND_MAP:
        run_command({command: True})
        COMMAND_MAP[0][1].return_value.action.assert_called_once()


@pytest.mark.parametrize('args',
                         [{'<name>': 'Capitalized-Name',
                           '-i': False, '--retries': '5'},
                          {'-i': True, '<name>': 'foo', '--retries': '5'},
                          {'-i': True, '<name>': 'foo', '--retries': '8'}])
@patch('mlt.main.docopt')
@patch('mlt.main.run_command')
def test_main_various_args(run_command, docopt, args):
    docopt.return_value = args
    # add common args and expected arg manipulations
    args['--namespace'] = 'foo'
    args['--retries'] = int(args['--retries'])
    args['--interactive'] = True
    args['<name>'] = args['<name>']
    main()
    run_command.assert_called_with(args)


@patch('mlt.main.docopt')
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
        run_command(args)


@patch('mlt.main.docopt')
def test_main_invalid_namespace(docopt_mock):
    """ Test that an invalid namespace throws a ValueError """
    args = {
        "<name>": "foo",
        # underscore should not be allowed in namespace
        "--namespace": "foo_bar",
        "-i": False,
        "--retries": 5
    }
    docopt_mock.return_value = args
    with pytest.raises(ValueError):
        main()
        run_command(args)

@pytest.mark.parametrize("command", [
    "set",
    "remove"
])
@patch('mlt.main.docopt')
def test_main_set_remove_name(docopt_mock, command):
    """ Ensure that set and unset commands require name arg."""
    args = {
        command: True,
        "--namespace": "foo",
        "<name>": "",
        "-i": False,
        "--retries": 5
    }
    docopt_mock.return_value = args
    with pytest.raises(ValueError):
        main()
        run_command(args)
