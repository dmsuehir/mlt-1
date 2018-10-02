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

from mock import MagicMock

from mlt.commands.undeploy import UndeployCommand
import pytest
from test_utils.io import catch_stdout


@pytest.fixture
def os_path_exists_mock(patch):
    return patch('os.path.exists')


@pytest.fixture
def is_custom_mock(patch):
    return patch('files.is_custom')


@pytest.fixture
def error_handling_mock(patch):
    return patch('error_handling.colored', MagicMock(
        side_effect=lambda x, _: x))


@pytest.fixture
def open_mock(patch):
    return patch('open')


@pytest.fixture
def proc_helpers(patch):
    return patch('process_helpers')


@pytest.fixture
def subprocess_mock(patch):
    return patch('subprocess.check_output')


@pytest.fixture
def get_sync_spec_mock(patch):
    return patch('sync_helpers.get_sync_spec')


@pytest.fixture(autouse=True)
def load_config_mock(patch):
    return patch('config_helpers.load_config',
                 MagicMock(return_value={'name': 'foo',
                                         'namespace': 'bar'}))


@pytest.fixture
def get_deployed_jobs_mock(patch):
    return patch('files.get_deployed_jobs')


@pytest.fixture
def remove_job_dir_mock(patch):
    return patch('UndeployCommand.remove_job_dir')


def undeploy_fail(fail_text, command):
    """asserts we get some output along with a SystemExit"""
    with catch_stdout() as output:
        with pytest.raises(SystemExit):
            UndeployCommand(command).action()
        assert output.getvalue().strip() == fail_text


def test_undeploy_custom(get_sync_spec_mock, is_custom_mock, open_mock,
                         os_path_exists_mock, subprocess_mock,
                         remove_job_dir_mock, get_deployed_jobs_mock):
    """
    Tests successful call to the undeploy command with a custom deploy
    """
    get_sync_spec_mock.return_value = None
    is_custom_mock.return_value = True
    os_path_exists_mock.return_value = True
    subprocess_mock.return_value = b"Successful Custom Undeploy"
    remove_job_dir_mock.input_value = 'k8s/job1'
    get_deployed_jobs_mock.return_value = ["job1"]

    with catch_stdout() as output:
        UndeployCommand({'undeploy': True}).action()
        assert output.getvalue().strip() == "Successful Custom Undeploy"


def test_undeploy_custom_no_app_deployed(open_mock, get_sync_spec_mock,
                                         is_custom_mock, os_path_exists_mock,
                                         get_deployed_jobs_mock):
    """Custom deploy when the app isn't deployed, we should get error"""
    get_sync_spec_mock.return_value = None
    is_custom_mock.return_value = True
    os_path_exists_mock.return_value = False
    get_deployed_jobs_mock.return_value = {}
    command = {'undeploy': True}
    subprocess_mock.return_value = b"Successful Custom Undeploy"

    undeploy_fail("This app has not been deployed yet.", command)


def test_undeploy_custom_multiple_jobs_deployed(
        open_mock, get_deployed_jobs_mock, get_sync_spec_mock,
        is_custom_mock, os_path_exists_mock):
    """if running `mlt undeploy` while multiple jobs found
    return an error"""
    get_sync_spec_mock.return_value = None
    is_custom_mock.return_value = True
    get_deployed_jobs_mock.return_value = ["job1", "job2"]
    command = {'undeploy': True}
    os_path_exists_mock.return_value = True

    undeploy_fail("Multiple jobs are found under this application, " +
                  "please try `mlt undeploy --all` or specify a single" +
                  " job to undeploy using " +
                  "`mlt undeploy --job-name <job-name>`", command)


def test_undeploy_custom_by_job_name(
        open_mock, get_deployed_jobs_mock, remove_job_dir_mock,
        get_sync_spec_mock, is_custom_mock, subprocess_mock,
        os_path_exists_mock):
    """test `mlt undeploy --job-name` with custom undeploy."""
    get_sync_spec_mock.return_value = None
    is_custom_mock.return_value = True
    subprocess_mock.return_value = b"Successful Custom Undeploy"
    get_deployed_jobs_mock.return_value = ["job1", "job2"]
    os_path_exists_mock.return_value = True
    remove_job_dir_mock.input_value = 'k8s/job1'
    with catch_stdout() as output:
        UndeployCommand({'undeploy': True, '--job-name': 'job1'}).action()
        assert output.getvalue().strip() == "Successful Custom Undeploy"


def test_undeploy_custom_all(
        open_mock, get_deployed_jobs_mock, remove_job_dir_mock,
        get_sync_spec_mock, is_custom_mock, subprocess_mock,
        os_path_exists_mock):
    """test `mlt undeploy --all."""
    get_sync_spec_mock.return_value = None
    is_custom_mock.return_value = True
    subprocess_mock.return_value = b"Successful Custom Undeploy"
    get_deployed_jobs_mock.return_value = ["job1", "job2"]
    os_path_exists_mock.return_value = True
    remove_job_dir_mock.input_value = 'k8s/job1'
    with catch_stdout() as output:
        UndeployCommand({'undeploy': True, '--all': True}).action()
        assert output.getvalue().strip() == 'Successful Custom Undeploy' \
                                            '\nSuccessful Custom Undeploy'


def test_undeploy(load_config_mock, proc_helpers, remove_job_dir_mock,
                  get_deployed_jobs_mock):
    """simple undeploy"""
    remove_job_dir_mock.input_value = 'k8s/job1'
    get_deployed_jobs_mock.return_value = ["job1"]
    UndeployCommand({'undeploy': True}).action()
    proc_helpers.run.assert_called_once()


def test_undeploy_custom_delete_job_dir(
        open_mock, get_deployed_jobs_mock, get_sync_spec_mock,
        is_custom_mock, subprocess_mock, os_path_exists_mock):
    """test removing job dir while undeploying it."""
    get_sync_spec_mock.return_value = None
    is_custom_mock.return_value = True
    subprocess_mock.return_value = b"No such file or directory: 'k8s/job1'"
    get_deployed_jobs_mock.return_value = ["job1"]
    os_path_exists_mock.return_value = True
    with catch_stdout() as output:
        with pytest.raises(OSError):
            UndeployCommand({'undeploy': True}).action()
        assert"No such file or directory: 'k8s/job1'" in output.getvalue()


def test_undeploy_by_job_name(proc_helpers, remove_job_dir_mock,
                              get_deployed_jobs_mock):
    """tests `mlt undeploy --job-name` to undeploy a job."""
    remove_job_dir_mock.input_value = 'k8s/job1'
    get_deployed_jobs_mock.return_value = ["job1"]
    UndeployCommand({'undeploy': True, '--job-name': 'job1'}).action()
    proc_helpers.run.assert_called_once()


def test_undeploy_by_bad_job_name(
        remove_job_dir_mock, get_deployed_jobs_mock):
    """tests `mlt undeploy --job-name` with a non existing job name."""
    remove_job_dir_mock.input_value = 'k8s/job1'
    get_deployed_jobs_mock.return_value = ["job1"]
    command = {'undeploy': True, '--job-name': 'job2'}
    with catch_stdout() as output:
        with pytest.raises(SystemExit):
            UndeployCommand(command).action()
        assert"Job name job2 not found" in output.getvalue()


def test_undeploy_synced(error_handling_mock, get_sync_spec_mock):
    """undeploying a synced job, we need to delete the sync first"""
    get_sync_spec_mock.return_value = 'hello-world'
    command = {'undeploy': True}
    undeploy_fail("This app is currently being synced, please run " +
                  "`mlt sync delete` to unsync first", command)
