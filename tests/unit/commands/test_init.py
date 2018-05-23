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

import os
import uuid
import shutil

import pytest

from mlt.commands.init import InitCommand
from mlt.utils import constants
from test_utils import project
from test_utils.io import catch_stdout


@pytest.fixture
def checking_crds_mock(patch):
    return patch('kubernetes_helpers.checking_crds_on_k8')


@pytest.fixture
def open_mock(patch):
    return patch('open')


@pytest.fixture
def copytree_mock(patch):
    return patch('copytree')


@pytest.fixture
def copy_tree_mock(patch):
    return patch('git_helpers.copy_tree')


@pytest.fixture
def process_helpers(patch):
    return patch('process_helpers')


@pytest.fixture
def check_output_mock(patch):
    return patch('check_output')


@pytest.fixture
def config_helpers_mock(patch):
    return patch('config_helpers')


def test_init_dir_exists():
    new_dir = str(uuid.uuid4())
    os.mkdir(new_dir)
    init_dict = {
        'init': True,
        '--template': 'hello-world',
        '<name>': new_dir,
        '--skip-crd-check': True,
        '--template-repo': project.basedir()
    }
    try:
        with catch_stdout() as caught_output:
            with pytest.raises(SystemExit) as bad_init:
                InitCommand(init_dict).action()
                assert caught_output.getvalue() == \
                       "Directory '{}' already exists: delete ".format(
                           new_dir) + "before trying to initialize new " + \
                       "application"
                assert bad_init.value.code == 1
    finally:
        os.rmdir(new_dir)


def test_init(open_mock, process_helpers, copytree_mock, check_output_mock,
              config_helpers_mock, copy_tree_mock):
    check_output_mock.return_value.decode.return_value = 'bar'
    new_dir = str(uuid.uuid4())

    init_dict = {
        'init': True,
        '--template': 'hello-world',
        '--template-repo': project.basedir(),
        '--registry': None,
        '--namespace': None,
        '--skip-crd-check': True,
        '<name>': new_dir
    }
    config_helpers_mock.get_template_parameters_from_file.return_value = [{"name": "greeting", "value": "hello"}]
    init = InitCommand(init_dict)
    init.action()
    assert init.app_name == new_dir


def test_init_crd_check(checking_crds_mock, process_helpers, check_output_mock,
                        copy_tree_mock):
    new_dir = str(uuid.uuid4())
    init_dict = {
        'init': True,
        '--template': 'tf-distributed',
        '--template-repo': project.basedir(),
        '--registry': True,
        '--namespace': None,
        '--skip-crd-check': False,
        '<name>': new_dir
    }
    checking_crds_mock.return_value = {'tfjobs.kubeflow.org'}
    init = InitCommand(init_dict)
    try:
        with catch_stdout() as caught_output:
            init.action()
            output = caught_output.getvalue()

        message_code = output.find("tfjobs.kubeflow.org")
        assert message_code >= 0
    finally:
        shutil.rmtree(new_dir)


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
    template_params = [{'name': 'num_ps', 'value': '1'},
                       {'name': 'num_workers', 'value': '2'}]
    result = init._build_mlt_json(template_params)
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
    result = init._build_mlt_json(template_params)
    assert constants.TEMPLATE_PARAMETERS not in result
