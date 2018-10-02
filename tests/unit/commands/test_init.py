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

import errno
import uuid

import pytest
from mock import MagicMock

from mlt.commands.init import InitCommand
from mlt.utils import constants
from test_utils import project
from test_utils.io import catch_stdout


@pytest.fixture
def checking_crds_mock(patch):
    return patch('kubernetes_helpers.checking_crds_on_k8')


@pytest.fixture
def open_mock(patch):
    open_mock = MagicMock()
    data = MagicMock()
    data.readlines.return_value = """
- name: $app
#       ### BEGIN KSYNC SECTION
#       command: ['/bin/sh']
#       args: ['-c', 'python main.py; tail -f /dev/null']
#       ### END KSYNC SECTION
""".split('\n')
    open_mock.return_value.__enter__.return_value = data
    return patch('open', open_mock)


@pytest.fixture
def os_path_exists_mock(patch):
    return patch('os.path.exists')


@pytest.fixture
def os_path_isdir_mock(patch):
    return patch('os.path.isdir')


@pytest.fixture
def colored_mock(patch):
    return patch('error_handling.colored', MagicMock(
        side_effect=lambda x, _: x))


@pytest.fixture
def copytree_mock(patch):
    return patch('copytree')


@pytest.fixture()
def copyfile_mock(patch):
    return patch('copyfile')


@pytest.fixture()
def binary_path_mock(patch):
    return patch('localhost_helpers.binary_path')


@pytest.fixture()
def listdir_mock(patch):
    return patch('os.listdir')


@pytest.fixture()
def update_yaml_for_sync_mock(patch):
    return patch('InitCommand._check_update_yaml_for_sync')


@pytest.fixture()
def init_git_repo_mock(patch):
    return patch('InitCommand._init_git_repo')


@pytest.fixture
def process_helpers(patch):
    return patch('process_helpers')


@pytest.fixture
def check_output_mock(patch):
    return patch('check_output')


@pytest.fixture
def config_helpers_mock(patch):
    return patch('config_helpers')


@pytest.fixture
def copy_mock(patch):
    return patch('copy')


@pytest.fixture
def get_template_params_mock(patch):
    return patch('config_helpers.get_template_parameters_from_file')


@pytest.fixture
def traceback_mock(patch):
    return patch('traceback')


@pytest.fixture
def yaml_load_mock(patch):
    return patch('yaml.load')


@pytest.fixture(autouse=True)
def clone_repo_mock(patch):
    clone_mock = MagicMock()
    clone_mock.return_value.__enter__.return_value = 'bar'
    return patch('git_helpers.clone_repo', clone_mock)


@pytest.fixture(autouse=True)
def get_latest_sha_mock(patch):
    return patch('git_helpers.get_latest_sha')


@pytest.fixture(autouse=True)
def json_dump_mock(patch):
    return patch('json.dump')


@pytest.mark.parametrize('errno_op', [errno.EEXIST, errno.ESRCH])
def test_init_dir_exists(open_mock, process_helpers, copytree_mock,
                         check_output_mock, config_helpers_mock,
                         colored_mock, traceback_mock, errno_op):
    new_dir = str(uuid.uuid4())
    init_dict = {
        'init': True,
        '--template': 'hello-world',
        '<name>': new_dir,
        '--skip-crd-check': True,
        '--template-repo': project.basedir()
    }
    copytree_mock.side_effect = OSError(errno_op, 'error')
    with catch_stdout() as caught_output:
        with pytest.raises(SystemExit) as bad_init:
            InitCommand(init_dict).action()

        assert bad_init.value.code == 1
        if errno_op == errno.EEXIST:
            assert \
                caught_output.getvalue().strip() == \
                "Directory '{}' already exists: delete ".format(
                    new_dir) + "before trying to initialize new " \
                               "application"
        else:
            traceback_mock.format_exc.assert_called_once()


def test_init(open_mock, process_helpers, copytree_mock, check_output_mock,
              config_helpers_mock):
    check_output_mock.return_value.decode.return_value = 'bar'
    new_dir = str(uuid.uuid4())

    init_dict = {
        'init': True,
        '--template': 'hello-world',
        '--template-repo': project.basedir(),
        '--registry': None,
        '--namespace': None,
        '--skip-crd-check': True,
        '--enable-sync': False,
        '<name>': new_dir
    }
    config_helpers_mock.get_template_parameters_from_file.return_value = \
        [{"name": "greeting", "value": "hello"}]
    init = InitCommand(init_dict)
    init.action()
    assert init.app_name == new_dir


def test_init_enable_sync(open_mock, process_helpers, copytree_mock,
                          check_output_mock, config_helpers_mock,
                          copyfile_mock, listdir_mock,
                          binary_path_mock, os_path_exists_mock):
    check_output_mock.return_value.decode.return_value = 'bar'
    new_dir = str(uuid.uuid4())

    init_dict = {
        'init': True,
        '--template': 'hello-world',
        '--template-repo': project.basedir(),
        '--registry': None,
        '--namespace': None,
        '--skip-crd-check': True,
        '--enable-sync': True,
        '<name>': new_dir
    }
    binary_path_mock.return_value = True
    config_helpers_mock.get_template_parameters_from_file.return_value = \
        [{"name": "greeting", "value": "hello"}]
    os_path_exists_mock.return_value = True
    listdir_mock.return_value = ['job.yaml']

    init = InitCommand(init_dict)
    init.action()
    assert init.app_name == new_dir


def test_init_ksync_missing(open_mock, process_helpers, copytree_mock,
                            check_output_mock, config_helpers_mock,
                            copyfile_mock, listdir_mock, binary_path_mock):
    check_output_mock.return_value.decode.return_value = 'bar'
    new_dir = str(uuid.uuid4())

    init_dict = {
        'init': True,
        '--template': 'hello-world',
        '--template-repo': project.basedir(),
        '--registry': None,
        '--namespace': None,
        '--skip-crd-check': True,
        '--enable-sync': True,
        '<name>': new_dir
    }
    binary_path_mock.return_value = False
    config_helpers_mock.get_template_parameters_from_file.return_value = \
        [{"name": "greeting", "value": "hello"}]
    with catch_stdout() as caught_output:
        with pytest.raises(SystemExit) as bad_init:
            InitCommand(init_dict).action()
            assert \
                caught_output.getvalue() == "ksync is not installed on " \
                                            "localhost"
            assert bad_init.value.code == 1


def test_init_sync_not_supported(open_mock, process_helpers, copytree_mock,
                                 check_output_mock, config_helpers_mock,
                                 copyfile_mock, listdir_mock,
                                 binary_path_mock, update_yaml_for_sync_mock,
                                 init_git_repo_mock):
    check_output_mock.return_value.decode.return_value = 'bar'
    new_dir = str(uuid.uuid4())

    init_dict = {
        'init': True,
        '--template': 'hello-world',
        '--template-repo': project.basedir(),
        '--registry': None,
        '--namespace': None,
        '--skip-crd-check': True,
        '--enable-sync': True,
        '<name>': new_dir
    }
    update_yaml_for_sync_mock.rerun_value = False
    init_git_repo_mock.return_value = False
    config_helpers_mock.get_template_parameters_from_file.return_value = \
        [{"name": "greeting", "value": "hello"}]
    init = InitCommand(init_dict)
    init.action()
    assert init.app_name == new_dir


def test_init_crd_check(open_mock, checking_crds_mock, process_helpers,
                        check_output_mock, copytree_mock, os_path_exists_mock):
    new_dir = str(uuid.uuid4())
    init_dict = {
        'init': True,
        '--template': 'tf-distributed',
        '--template-repo': project.basedir(),
        '--registry': True,
        '--namespace': None,
        '--skip-crd-check': False,
        '--enable-sync': False,
        '<name>': new_dir
    }
    checking_crds_mock.return_value = {'tfjobs.kubeflow.org'}
    # set crd_file as true since we don't actually create a dir
    os_path_exists_mock.return_value = True

    init = InitCommand(init_dict)
    with catch_stdout() as caught_output:
        init.action()
        output = caught_output.getvalue()

    message_code = output.find("tfjobs.kubeflow.org")
    assert message_code >= 0


def test_template_params():
    new_dir = str(uuid.uuid4())
    init_dict = {
        'init': True,
        '--template': 'tf-dist-mnist',
        '--template-repo': project.basedir(),
        '--registry': True,
        '--namespace': None,
        '<name>': new_dir
    }
    init = InitCommand(init_dict)
    template_params = [{'name': 'num_ps', 'value': 1},
                       {'name': 'num_workers', 'value': 2}]
    result = init._build_mlt_json(template_params, None)
    assert constants.TEMPLATE_PARAMETERS in result
    result_params = result[constants.TEMPLATE_PARAMETERS]
    for param in template_params:
        assert param["name"] in result_params
        assert param["value"] == result_params[param["name"]]


def test_no_template_params():
    new_dir = str(uuid.uuid4())
    init_dict = {
        'init': True,
        '--template': 'tf-dist-mnist',
        '--template-repo': project.basedir(),
        '--registry': True,
        '--namespace': None,
        '<name>': new_dir
    }
    init = InitCommand(init_dict)
    template_params = None
    result = init._build_mlt_json(template_params, None)
    assert constants.TEMPLATE_PARAMETERS not in result


@pytest.mark.parametrize('error', [
    "No such file or directory",
    "Warning:badness"
])
def test_no_gcloud_or_registry(open_mock, process_helpers, copytree_mock,
                               check_output_mock, config_helpers_mock, error):
    """No such file or directory" OSError to simulate gcloud not found
       With and without the error `No such file or directory`
       If there was a file or dir, then we `raise` the error triggered
    """
    check_output_mock.side_effect = OSError(error)
    new_dir = str(uuid.uuid4())
    init_dict = {
        'init': True,
        '--template': 'tf-dist-mnist',
        '--template-repo': project.basedir(),
        '--namespace': 'test-namespace',
        '<name>': new_dir,
        '--registry': False,
        '--skip-crd-check': False,
        '--enable-sync': False
    }
    init = InitCommand(init_dict)

    with catch_stdout() as output:
        if "No such file or directory" in error:
            init.action()
            output = output.getvalue()
            assert "No registry name was provided and gcloud was not "\
                   "found.  Please set your container registry name" in output
        else:
            # raising OSError triggers a sys.exit(1) call in action()
            with pytest.raises(SystemExit):
                init.action()

    assert init.app_name == new_dir


def test_debug_on_fail_init(get_template_params_mock, copy_mock, copytree_mock,
                            open_mock, checking_crds_mock, check_output_mock,
                            process_helpers, os_path_isdir_mock, listdir_mock,
                            yaml_load_mock):
    """ Tests that when debug_on_fail is a template parameter, 'copy' is
    called, since we copy the kubernetes debug wrapper to the app. """
    get_template_params_mock.return_value = [{'name': 'debug_on_fail',
                                              'value': 'false'}]
    os_path_isdir_mock.return_value = True
    listdir_mock.return_value = ["job.yaml"]
    yaml_load_mock.return_value = {
        "containers": [
            {"name": "container", "env":
                [{"name": "DEBUG_ON_FAIL", "value": True}]},
            {"name": "container2", "env":
                [{"name": "random", "value": False}]}
        ]}

    new_dir = str(uuid.uuid4())
    init_dict = {
        'init': True,
        '--template': 'tf-dist-mnist',
        '--template-repo': project.basedir(),
        '--registry': True,
        '--namespace': None,
        '<name>': new_dir,
        '--skip-crd-check': False,
        '--enable-sync': False
    }
    init = InitCommand(init_dict)
    init.action()
    assert copy_mock.called
