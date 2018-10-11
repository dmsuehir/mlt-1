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
from conditional import conditional
from contextlib import contextmanager

from subprocess import CalledProcessError

import pytest
from mock import MagicMock
from test_utils.io import catch_stdout

from mlt.commands.status import StatusCommand


@pytest.fixture
def init_mock(patch):
    return patch('config_helpers.load_config')


@pytest.fixture
def get_deployed_jobs(patch):
    return patch('files.get_deployed_jobs', lambda: ['k8s/job1'])


@pytest.fixture
def get_job_kinds(patch):
    job_kinds = MagicMock(return_value=({'custom'}, True))
    return patch('files.get_job_kinds', job_kinds)


@pytest.fixture
def is_custom_mock(patch):
    return patch('files.is_custom', lambda x: True)


@pytest.fixture
def isfile_mock(patch):
    return patch('os.path.isfile')


@pytest.fixture
def getmtime_mock(patch):
    return patch('os.path.getmtime')


@pytest.fixture
def listdir_mock(patch):
    return patch('os.listdir')


@pytest.fixture
def open_mock(patch):
    return patch('open')


@pytest.fixture
def subprocess_mock(patch):
    return patch('subprocess.check_output')


@pytest.fixture
def run_popen_mock(patch):
    return patch('process_helpers.run_popen')


@pytest.fixture
def default_status_mock(patch):
    return patch('StatusCommand._default_status')


@pytest.fixture()
def get_sync_spec_mock(patch):
    return patch('sync_helpers.get_sync_spec')


def status(count=1, catch_exception=None):
    status_cmd = StatusCommand({'<count>': count})
    status_cmd.config = {'name': 'app', 'namespace': 'namespace'}

    with catch_stdout() as caught_output:
        with conditional(catch_exception, pytest.raises(catch_exception)):
            status_cmd.action()
        output = caught_output.getvalue()
    return output


@contextmanager
def check_different_valid_statuses(job_kind, init_mock, isfile_mock,
                                   run_popen_mock, subprocess_mock):
    """
    Wrapper to help prep subprocess mocks and then check their output
    """
    # hack to grab what code being wrapped returned
    output = type("OutputGrabber", (object,), {})

    if job_kind == 'job':
        generic_status = "Successful normal pod status"
        run_popen_mock.return_value.wait.side_effect = lambda: print(
            generic_status)

        yield output
        assert generic_status in output.wrapper_data

    elif job_kind in ('tfjob', 'pytorchjob'):
        crd_info = MagicMock()
        crd_status = "Successful crd status"
        crd_info.communicate.return_value = (
            bytearray(crd_status, 'utf-8'), "")
        crd_info.wait.return_value = 0
        run_popen_mock.side_effect = [crd_info, MagicMock()]

        yield output
        assert crd_status in output.wrapper_data
        assert "CRD: " in output.wrapper_data
        assert "Pods: " in output.wrapper_data

    else:
        custom_status = "Successful custom status"
        subprocess_mock.return_value = bytearray(custom_status, 'utf-8')

        yield output
        assert custom_status in output.wrapper_data


def test_uninitialized_status():
    """
    Tests calling the status command before this app has been initialized.
    """
    with catch_stdout() as caught_output:
        with pytest.raises(SystemExit):
            StatusCommand({})
        output = caught_output.getvalue()
        expected_error = "This command requires you to be in an `mlt init` " \
                         "built directory"
        assert expected_error in output


@pytest.mark.parametrize('job_kind', [
    'job', 'tfjob', 'pytorchjob', 'experiment'])
def test_status(get_job_kinds, job_kind, init_mock, isfile_mock,
                run_popen_mock, subprocess_mock, get_sync_spec_mock):
    """
    Tests calling the status command on jobs
    Types of jobs: generic, crd, custom
    """
    get_sync_spec_mock.return_value = None

    with check_different_valid_statuses(
            job_kind, init_mock, isfile_mock,
            run_popen_mock, subprocess_mock) as output:
        get_job_kinds.return_value = ({job_kind}, True)
        output.wrapper_data = status()


def test_status_no_deploy(init_mock, open_mock, isfile_mock):
    """
    Tests calling the status command before this app has been deployed.
    """
    isfile_mock.return_value = False
    output = status(catch_exception=SystemExit)
    expected_output = "This app has not been deployed yet"
    assert expected_output in output


def test_status_custom_makefile(isfile_mock, init_mock, get_deployed_jobs,
                                get_sync_spec_mock, getmtime_mock,
                                get_job_kinds, subprocess_mock,
                                is_custom_mock):
    """
    Tests a custom status if 'status:' is in Makefile
    """
    isfile_mock.return_value = True
    custom_status = "Successful custom status"
    subprocess_mock.return_value = bytearray(custom_status, 'utf-8')
    output = status()
    assert custom_status in output
    assert subprocess_mock.is_called_once()


def test_successful_status_no_sync(init_mock, open_mock, isfile_mock,
                                   subprocess_mock, get_sync_spec_mock,
                                   listdir_mock, get_deployed_jobs,
                                   get_job_kinds, getmtime_mock):
    """
    Tests successful call to the status command.
    """
    isfile_mock.return_value = True
    get_sync_spec_mock.return_value = None
    expected_output = "Job and pod status"
    subprocess_mock.return_value.decode.return_value = expected_output
    status_output = status(count=2)
    assert expected_output in status_output


def test_successful_status_after_sync(init_mock, open_mock, isfile_mock,
                                      subprocess_mock, get_sync_spec_mock,
                                      listdir_mock, get_deployed_jobs,
                                      get_job_kinds, getmtime_mock):
    """
    Tests successful call to the status command.
    """
    isfile_mock.return_value = True
    get_sync_spec_mock.return_value = 'hello-world'
    expected_output = "Watched by sync"
    subprocess_mock.return_value.decode.return_value = expected_output
    status_output = status()
    assert expected_output in status_output


def test_status_not_in_makefile(init_mock, open_mock, isfile_mock,
                                subprocess_mock, listdir_mock,
                                get_deployed_jobs, get_job_kinds,
                                getmtime_mock):
    """
    Tests use case where status target is not in the Makefile.
    """
    isfile_mock.return_value = True
    expected_output = "This app does not support the `mlt status` command"
    subprocess_mock.side_effect = CalledProcessError(
        returncode=2, cmd="make status",
        output="No rule to make target `status'")
    status_output = status(catch_exception=SystemExit)
    assert expected_output in status_output


def test_status_makefile_error(init_mock, open_mock, isfile_mock,
                               subprocess_mock, get_job_kinds):
    """
    Tests use case where we get an error from executing the status command
    in the Makefile.
    """
    isfile_mock.return_value = True
    error_msg = "Makefile status target error"
    subprocess_mock.side_effect = CalledProcessError(
        returncode=2, cmd="make status", output=error_msg)
    status_output = status(catch_exception=SystemExit)
    assert error_msg in status_output
