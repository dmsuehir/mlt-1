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

from mlt.commands.status import StatusCommand


@pytest.fixture
def init_mock(patch):
    return patch('config_helpers.load_config')


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


def test_uninitialized_status():
    with catch_stdout() as caught_output:
        with pytest.raises(SystemExit):
            StatusCommand({})
        output = caught_output.getvalue()
    expected_error = "This command requires you to be in an `mlt init` " \
                     "built directory"
    assert expected_error in output
