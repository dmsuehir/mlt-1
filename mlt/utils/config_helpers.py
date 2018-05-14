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

import json
import os
import sys
from mlt.utils import constants


def load_config():
    """stores mlt.json data in self.config"""
    if os.path.isfile(constants.MLT_CONFIG):
        with open(constants.MLT_CONFIG) as f:
            return json.load(f)
    else:
        print("This command requires you to be in an `mlt init` "
              "built directory.")
        sys.exit(1)


def update_config(json_data):
    """overwrites the existing MLT config with the specified data"""
    with open(constants.MLT_CONFIG, "w") as f:
        json.dump(json_data, f, indent=2)


def get_template_parameters_from_file(file_path):
    """ Returns template parameters from the specified file """
    params = {}
    if os.path.isfile(file_path):
        with open(file_path) as f:
            params = get_template_parameters(json.load(f))

    return params


def get_template_parameters(config_dict):
    """
    Returns dictionary of template parameters, if it exists in the specified
    config.  Otherwise, returns empty dictionary.
    """
    return config_dict.get(constants.TEMPLATE_PARAMETERS, {})
