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

from __future__ import print_function

import pytest

from mock import patch, MagicMock
from subprocess import CalledProcessError
from test_utils.io import catch_stdout

from mlt.commands.status import StatusCommand


@pytest.fixture
def init_mock(patch):
    return patch('config_helpers.load_config')


@pytest.fixture
def isfile_mock(patch):
    return patch('os.path.isfile')

@pytest.fixture
def open_mock(patch):
    return patch('open')


@pytest.fixture
def json_mock(patch):
    return patch('json')


@pytest.fixture
def subprocess_mock(patch):
    return patch('subprocess.check_output')


def status():
    status_cmd = StatusCommand({})
    status_cmd.config = {'name': 'app', 'namespace': 'namespace'}

    with catch_stdout() as caught_output:
        status_cmd.action()
        output = caught_output.getvalue()
    return output


def test_uninitialized_status():
    """
    Tests calling the status command before the app has been initialized.
    """
    with catch_stdout() as caught_output:
        with pytest.raises(SystemExit):
            StatusCommand({})
        output = caught_output.getvalue()
        expected_error = "This command requires you to be in an `mlt init` " \
                         "built directory"
        assert expected_error in output


def test_status_no_deploy(init_mock, open_mock, isfile_mock):
    """
    Tests calling the status command before the app has been deployed.
    """
    isfile_mock.return_value = False
    status = StatusCommand({})

    with catch_stdout() as caught_output:
        with pytest.raises(SystemExit):
            status.action()
        output = caught_output.getvalue()
        expected_output = "This application has not been deployed yet."
        assert expected_output in output


def test_successful_status(init_mock, open_mock, isfile_mock,
                           json_mock, subprocess_mock):
    """
    Tests successful call to the status command.
    """
    isfile_mock.return_value = True
    json_mock.load.return_value = {"app_run_id": "123-456-789"}
    expected_output = "Job and pod status"
    subprocess_mock.return_value.decode.return_value = expected_output
    status_output = status()
    assert expected_output in status_output


@patch('mlt.commands.status.StatusCommand._default_status')
def test_status_not_in_makefile(default_status_mock, init_mock, open_mock,
                                isfile_mock, json_mock, subprocess_mock):
    """
    Tests use case where status target is not in the Makefile.
    """
    isfile_mock.return_value = True
    json_mock.load.return_value = {"app_run_id": "123-456-789"}
    expected_default_status = "default status output"
    default_status_mock.return_value = expected_default_status
    subprocess_mock.side_effect = CalledProcessError(
        returncode=2, cmd="make status",
        output="No rule to make target `status'")

    status_output = status()
    assert expected_default_status in status_output


def test_status_makefile_error(init_mock, open_mock, isfile_mock, json_mock,
                               subprocess_mock):
    """
    Tests use case where we get an error from executing the status command
    in the Makefile.
    """
    isfile_mock.return_value = True
    json_mock.load.return_value = {"app_run_id": "123-456-789"}
    error_msg = "Makefile status target error"
    subprocess_mock.side_effect = CalledProcessError(
        returncode=2, cmd="make status", output=error_msg)
    status_output = status()
    assert error_msg in status_output


def test_default_status_command():
    """
    Tests for the default status comamnd which is used when we don't find
    the status target in the Makefile
    """
    pass
