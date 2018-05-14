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
# Unless required by applicable law or agreed to in writing, software`
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: EPL-2.0
#

import sys
from tabulate import tabulate

from mlt.commands import Command
from mlt.utils import config_helpers, constants


class ConfigCommand(Command):
    def __init__(self, args):
        super(ConfigCommand, self).__init__(args)
        self.list = args.get('list', False)
        self.set = args.get('set', False)
        self.unset = args.get('unset', False)
        self.name = args.get('<name>', None)
        self.value = args.get('<value>', None)
        self.config = config_helpers.load_config()

        self.param_keys = self.name.split('.') if self.name else None

        if (self.set or self.unset) and not self.name:
            print("Name of the configuration parameter must be specified.")
            sys.exit(1)

    def action(self):
        # Call the specified sub-command
        if self.list:
            print("list")
            self._list_configs()
        elif self.set:
            print("set")
            self._set_config()
        elif self.unset:
            print("unset")
            self._unset_config()
        else:
            print("Invalid config command.  Must have one of the following"
                  "sub-command selected: list, set, unset.")
            sys.exit(1)

    def _list_configs(self):
        """
        Lists the config parameters and their values using tabulate.
        """
        config_list = []
        for config_name in self.config.keys():
            if config_name == constants.TEMPLATE_PARAMETERS:
                template_params = self.config[config_name]
                for template_config in template_params.keys():
                    config_list.append(["{}.{}".format(
                        constants.TEMPLATE_PARAMETERS, template_config),
                        template_params[template_config]])
            else:
                config_list.append([config_name, self.config[config_name]])

        if len(config_list) > 0:
            print(tabulate(config_list, headers=['App Config', 'Value']))
        else:
            print("No configuration parameters to display.")

    def _set_config(self):
        """
        Sets the config parameter to the specified value.  If the config
        parameter does not already exist in the MLT config, then it's added.
        Writes the new config back to the mlt config file.
        """
        # Find or add the specified config
        matched_config = self.config
        for n in self.param_keys[:-1]:
            if n in matched_config:
                matched_config = matched_config[n]
            else:
                matched_config[n] = {}

        # Set the config value then write it back to the config file.
        matched_config[self.param_keys[-1]] = self.value
        config_helpers.update_config(self.config)

    def _unset_config(self):
        """
        Finds, then removes the specified config parameter from the MLT config
        file.  If the config parameter does not exist in the MLT config file,
        then an error is displayed.
        """
        matched_config = self.config
        key_not_found = "Unable to find config '{}'.\nTo see " \
                        "list of configs, use `mlt config list`.". \
            format(self.name)

        # Find the specified config, and display an error if it does not exist.
        for n in self.param_keys[:-1]:
            if n in matched_config:
                matched_config = matched_config[n]
            else:
                print(key_not_found)
                sys.exit(1)

        # Delete the config parameter and then write it back to the config file
        if self.param_keys[-1] in matched_config:
            del matched_config[self.param_keys[-1]]
        else:
            print(key_not_found)
            sys.exit(1)
        config_helpers.update_config(self.config)
