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

import re

from test_utils.e2e_commands import CommandTester


# NOTE: you need to deploy first before you deploy with --no-push
# otherwise you have no image to use to make new container from

class TestConfig(CommandTester):
    def test_config_list(self):
        """
        Tests listing configs in an init directory
        """
        self.init()
        self.config(subcommand="list")

    def test_update_config(self):
        """
        Tests the `name` config and then checks the config list to ensure that
        the new `name` is listed.
        """
        self.init()

        # list the configs
        original_configs, _ = self.config(subcommand="list")

        # set the `name` config to `foo`
        new_name = "foo"
        self.config(subcommand="set", config_name="name",
                    config_value=new_name)

        # list the configs again and compare to ensure the `name` was updated.
        updated_configs, _ = self.config(subcommand="list")
        assert updated_configs != original_configs
        p = re.compile(r"name[\s]+{}".format(new_name))
        assert p.search(str(updated_configs))

    def test_add_remove_config(self):
        """
        Tests adding a new config, and then lists the configs to ensure that
        new config is listed.  Remove the config and then lists the configs to
        ensure that the config has been removed.
        """
        self.init()

        # list the configs
        original_configs, _ = self.config(subcommand="list")

        # add a new config named `foo`
        new_config = "foo"
        new_value = "bar"
        self.config(subcommand="set", config_name=new_config,
                    config_value=new_value)

        # list the configs again to ensure that the new config is added.
        updated_configs, _ = self.config(subcommand="list")
        assert updated_configs != original_configs
        p = re.compile(r"{}[\s]+{}".format(new_config, new_value))
        assert p.search(str(updated_configs))

        # remove the config and then ensure that the config has been removed.
        self.config(subcommand="remove", config_name=new_config)
        updated_configs, _ = self.config(subcommand="list")
        p = re.compile(r"{}[\s]+{}".format(new_config, new_value))
        assert not p.search(str(updated_configs))
