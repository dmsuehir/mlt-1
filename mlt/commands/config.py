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
from tabulate import tabulate

from mlt.commands import Command
from mlt.utils import config_helpers, constants, error_handling


class TemplateConfigCommand(Command):
    def __init__(self, args):
        super(TemplateConfigCommand, self).__init__(args)
        self.config = config_helpers.load_config()
        self.param_keys = args.get('<name>').split('.') \
            if args.get('<name>') else []

    def action(self):
        # Call the specified sub-command
        if self.args.get('list'):
            self._list_configs()
        elif self.args.get('set'):
            self._set_config(self.param_keys, self.args.get('<value>'))
        elif self.args.get('remove'):
            self._remove_config(self.param_keys)

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

        if config_list:
            print(tabulate(config_list, headers=['Parameter Name', 'Value']))
        else:
            print("No configuration parameters to display.")

    def _find_config(self, param_keys, add_if_not_found,
                     key_not_found_error=""):
        """
        Finds the specified parameter in the config.  If add_if_not_found is
        True, then the parameter is added if it does not exist.  Otherwise,
        throws an error.
        """
        matched_config = self.config
        for n in param_keys[:-1]:
            if n in matched_config:
                matched_config = matched_config[n]
            else:
                if add_if_not_found:
                    matched_config[n] = {}
                else:
                    error_handling.throw_error(key_not_found_error)

        return matched_config

    def _set_config(self, param_keys, value):
        """
        Sets the config parameter to the specified value.  If the config
        parameter does not already exist in the MLT config, then it's added.
        Writes the new config back to the mlt config file.
        """
        # Find or add the specified config
        matched_config = self._find_config(param_keys, add_if_not_found=True)

        # Set the config value then write it back to the config file.
        matched_config[param_keys[-1]] = value
        config_helpers.update_config(self.config)

    def _remove_config(self, param_keys):
        """
        Finds, then removes the specified config parameter from the MLT config
        file.  If the config parameter does not exist in the MLT config file,
        then an error is displayed.
        """
        key_not_found = "Unable to find config '{}'. To see " \
                        "list of configs, use `mlt template_config list`.". \
            format(self.args.get('<name>'))

        # Find the specified config, and display an error if it does not exist.
        matched_config = self._find_config(param_keys, add_if_not_found=False,
                                           key_not_found_error=key_not_found)

        # Delete the config parameter and then write it back to the config file
        if param_keys[-1] in matched_config:
            del matched_config[param_keys[-1]]
        else:
            error_handling.throw_error(key_not_found)
        config_helpers.update_config(self.config)
