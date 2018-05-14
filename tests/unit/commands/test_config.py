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
import re

from test_utils.io import catch_stdout

from mlt.commands.config import ConfigCommand
from mlt.utils import constants


@pytest.fixture
def init_mock(patch):
    return patch('config_helpers.load_config')


@pytest.fixture
def update_config_mock(patch):
    return patch('config_helpers.update_config')


def config(list=False, set=False, unset=False, name=None, value=None):
    config_cmd = ConfigCommand({"list": list, "set": set, "unset": unset,
                                "<name>": name, "<value>": value})

    with catch_stdout() as caught_output:
        config_cmd.action()
        output = caught_output.getvalue()
    return output


def test_uninitialized_config_call():
    """
    Tests calling the config command before the app has been initialized.
    """
    with catch_stdout() as caught_output:
        with pytest.raises(SystemExit):
            ConfigCommand({})
        output = caught_output.getvalue()
        expected_error = "This command requires you to be in an `mlt init` " \
                         "built directory"
        assert expected_error in output


def test_invalid_subcommand(init_mock):
    """
    Tests calling the config command without a valid subcommand
    """
    init_mock.load_config.return_value = {}
    with catch_stdout() as caught_output:
        with pytest.raises(SystemExit):
            cmd = ConfigCommand({"list": False, "set": False, "unset": False})
            cmd.action()
        output = caught_output.getvalue()
        assert "Invalid config command" in output


@pytest.mark.parametrize("set_param, unset_param, name_param", [
    (True, False, None),
    (True, False, ""),
    (False, True, None),
    (False, True, "")
])
def test_no_parameter(init_mock, set_param, unset_param, name_param):
    """
    Tests that both the set and unset commands require the name arg
    """
    expected_error = "Name of the configuration parameter must be specified"
    with catch_stdout() as caught_output:
        with pytest.raises(SystemExit):
            config(set=set_param, unset=unset_param, name=name_param)
        output = caught_output.getvalue()
        assert expected_error in output


def test_list_config(init_mock):
    """
    Test calling the config list command and checks the output.
    """
    init_mock.return_value = {
        "namespace": "foo",
        "registry": "bar",
        constants.TEMPLATE_PARAMETERS: {
            "num_workers": 2
        }
    }
    output = config(list=True)

    p = re.compile("namespace[\s]+foo")
    assert p.search(output)
    p = re.compile("registry[\s]+bar")
    assert p.search(output)
    p = re.compile("{}.num_workers[\s]+2".format(
        constants.TEMPLATE_PARAMETERS))
    assert p.search(output)


def test_list_empty_configs(init_mock):
    """
    Tests calling the config list command when there are no configs. 
    """
    init_mock.return_value = {}
    output = config(list=True)
    assert "No configuration parameters to display." in output


def test_set_existing_config(init_mock, update_config_mock):
    """
    Tests modifying an existing config parameter
    """
    mlt_config = {
        "namespace": "foo",
        "registry": "bar",
        constants.TEMPLATE_PARAMETERS: {
            "num_workers": 2
        }
    }
    init_mock.return_value = mlt_config
    modified_parameter = "namespace"
    new_value = "new-namespace"
    config(set=True, name=modified_parameter, value=new_value)
    mlt_config[modified_parameter] = new_value
    update_config_mock.assert_called_with(mlt_config)


def test_set_new_config(init_mock, update_config_mock):
    """
    Tests setting a new config parameter, and ensures that the parameter is
    added to the config file.
    """
    mlt_config = {
        "namespace": "foo",
        "registry": "bar",
        constants.TEMPLATE_PARAMETERS: {
            "num_workers": 2
        }
    }
    init_mock.return_value = mlt_config
    new_parameter = "new_parameter"
    new_value = "new_value"
    config(set=True, name=new_parameter, value=new_value)
    mlt_config[new_parameter] = new_value
    update_config_mock.assert_called_with(mlt_config)


def test_set_existing_template_parameter(init_mock, update_config_mock):
    """
    Tests modifying an existing template parameter
    """
    mlt_config = {
        "namespace": "foo",
        "registry": "bar",
        constants.TEMPLATE_PARAMETERS: {
            "num_workers": 2
        }
    }
    init_mock.return_value = mlt_config
    modified_parameter = "{}.num_workers".format(constants.TEMPLATE_PARAMETERS)
    new_value = 4
    config(set=True, name=modified_parameter, value=new_value)
    mlt_config[constants.TEMPLATE_PARAMETERS][modified_parameter] = new_value
    update_config_mock.assert_called_with(mlt_config)


def test_set_unset_new_template_parameter(init_mock, update_config_mock):
    """
    Tests setting a new template parameter, ensures that the parameter is
    added to the config file, then unsets the parameter.
    """
    mlt_config = {
        "namespace": "foo",
        "registry": "bar",
        constants.TEMPLATE_PARAMETERS: {
            "num_workers": 2
        }
    }
    init_mock.return_value = mlt_config

    # Set new template parameter
    new_parameter = "{}.num_ps".format(constants.TEMPLATE_PARAMETERS)
    new_value = 1
    config(set=True, name=new_parameter, value=new_value)

    # Check that the config update was called with the new parameter
    expected_parameter = mlt_config
    expected_parameter[constants.TEMPLATE_PARAMETERS][new_parameter] = \
        new_value
    update_config_mock.assert_called_with(expected_parameter)

    # Unset the parameter, and we should be back to the original
    config(unset=True, name=new_parameter)
    update_config_mock.assert_called_with(mlt_config)


def test_set_unset_new_parameter(init_mock, update_config_mock):
    """
    Tests setting and unsetting a new parameter a few levels deep.
    """
    mlt_config = {
        "namespace": "foo",
        "registry": "bar",
        constants.TEMPLATE_PARAMETERS: {
            "num_workers": 2
        }
    }
    init_mock.return_value = mlt_config

    # Set new parameter
    new_parameter = "foo1.foo2.foo3"
    new_value = "new_value"
    config(set=True, name=new_parameter, value=new_value)

    # check that the config update was called with the new parameter
    expected_config = mlt_config
    expected_config["foo1"] = {}
    expected_config["foo1"]["foo2"] = {}
    expected_config["foo1"]["foo2"]["foo3"] = new_value
    update_config_mock.assert_called_with(expected_config)

    # Unset the parameter and check that we are back to the original config
    config(unset=True, name=new_parameter)
    update_config_mock.assert_called_with(mlt_config)


def test_unset_config_param(init_mock, update_config_mock):
    """
    Tests removing an existing config
    """
    mlt_config = {
        "namespace": "foo",
        "registry": "bar",
        constants.TEMPLATE_PARAMETERS: {
            "num_workers": 2
        }
    }
    init_mock.return_value = mlt_config

    # Unset the registry parameter and check the config update arg
    config(unset=True, name="registry")
    expected_config = {
        "namespace": "foo",
        constants.TEMPLATE_PARAMETERS: {
            "num_workers": 2
        }
    }
    update_config_mock.assert_called_with(expected_config)


@pytest.mark.parametrize("param_name", [
    "does-not-exist",
    "{}.does-not-exist".format(constants.TEMPLATE_PARAMETERS),
    "subparam.does-not-exist"
])
def test_unset_invalid_param(init_mock, param_name):
    """
    Tests trying to remove a parameter that does not exist
    """
    mlt_config = {
        "namespace": "foo",
        "registry": "bar",
        constants.TEMPLATE_PARAMETERS: {
            "num_workers": 2
        }
    }
    init_mock.return_value = mlt_config

    # Unset the registry parameter and check the config update arg
    with pytest.raises(SystemExit):
        output = config(unset=True, name=param_name)
        assert "Unable to find config" in output
