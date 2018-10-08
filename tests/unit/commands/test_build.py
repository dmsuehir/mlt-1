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
from test_utils.io import catch_stdout

from mlt.commands.build import BuildCommand


@pytest.fixture
def init_mock(patch):
    return patch('config_helpers.load_config')


@pytest.fixture
def get_template_parameters_mock(patch):
    return patch('config_helpers.get_template_parameters')


@pytest.fixture
def open_mock(patch):
    return patch('open')


@pytest.fixture
def progress_bar_mock(patch):
    return patch('progress_bar')


@pytest.fixture
def popen_mock(patch):
    popen = MagicMock()
    popen.return_value.poll.return_value = 0  # success
    return patch('process_helpers.run_popen', popen)


@pytest.fixture
def prevent_deadlock_mock(patch):
    prevent_deadlock_mock = MagicMock()
    prevent_deadlock_mock.return_value.__enter__.return_value = None
    return patch('process_helpers.prevent_deadlock', prevent_deadlock_mock)


def test_simple_build(progress_bar_mock, popen_mock, prevent_deadlock_mock,
                      open_mock, init_mock):
    progress_bar_mock.duration_progress.side_effect = \
        lambda x, y, z: print('Building')

    build = BuildCommand({'build': True,
                          '--watch': False,
                          '--verbose': False})
    build.config = MagicMock()

    with catch_stdout() as caught_output:
        build.action()
        output = caught_output.getvalue()

    # assert that we started build, then did build process, then built
    starting = output.find('Starting build')
    building = output.find('Building')
    built = output.find('Built')
    assert all(var >= 0 for var in (starting, building, built))
    assert starting < building < built


def test_build_errors(popen_mock, progress_bar_mock, prevent_deadlock_mock,
                      open_mock, init_mock):
    popen_mock.return_value.poll.return_value = 1  # set to 1 for error
    output_str = "normal output..."
    error_str = "error message..."
    build_output = MagicMock()
    build_output.decode.return_value = output_str
    error_output = MagicMock()
    error_output.decode.return_value = error_str
    popen_mock.return_value.communicate.return_value = (build_output,
                                                        error_output)

    build = BuildCommand({'build': True,
                          '--watch': False,
                          '--verbose': False})
    build.config = MagicMock()

    with catch_stdout() as caught_output:
        with pytest.raises(SystemExit):
            build.action()
        output = caught_output.getvalue()

    # assert that we got the normal output and then the error output
    output_location = output.find(output_str)
    error_location = output.find(error_str)
    assert all(var >= 0 for var in (output_location, error_location))
    assert output_location < error_location


@patch('mlt.commands.build.time.sleep')
@patch('mlt.commands.build.Observer')
def test_watch_build(observer, sleep_mock, prevent_deadlock_mock, open_mock,
                     init_mock):
    sleep_mock.side_effect = KeyboardInterrupt

    build = BuildCommand({'build': True,
                          '--watch': True,
                          '--verbose': False})
    build.config = MagicMock()

    with patch('mlt.commands.build.EventHandler'):
        build.action()


def test_build_verbose(popen_mock, open_mock, init_mock):
    build = BuildCommand({'build': True,
                          '--watch': False,
                          '--verbose': True})
    build.config = MagicMock()

    with catch_stdout() as caught_output:
        build.action()
        output = caught_output.getvalue()

    # assert that we started build, then did build process, then built
    starting = output.find('Starting build')
    built = output.find('Built')
    assert all(var >= 0 for var in (starting, built))
    assert starting < built


@pytest.mark.parametrize("template_parameters", [
    {}, {'name': 'test'}])
def test_build_get_template_parameters(progress_bar_mock,
                                       popen_mock, prevent_deadlock_mock,
                                       open_mock, init_mock,
                                       template_parameters,
                                       get_template_parameters_mock):
    progress_bar_mock.duration_progress.side_effect = \
        lambda x, y, z: print('Building')

    build = BuildCommand({'build': True,
                          '--watch': False,
                          '--verbose': False})
    build.config = MagicMock()

    get_template_parameters_mock.return_value = template_parameters

    with catch_stdout() as caught_output:
        build.action()
        output = caught_output.getvalue()

    # assert that we started build, then did build process, then built
    starting = output.find('Starting build')
    building = output.find('Building')
    built = output.find('Built')
    assert all(var >= 0 for var in (starting, building, built))
    assert starting < building < built
