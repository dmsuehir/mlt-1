#! /bin/bash
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

# Execute training on each node, pulling local thread counts for the train script
cd /src/app

export physical_cores=`lscpu | grep "Core(s) per socket" | cut -d':' -f2 | sed "s/ //g"` # Total number of physical cores per socket

export num_threads=$(( ${1} * $physical_cores )) # Total number of physical cores on this machine

python main.py \
--num_inter_threads=${2} \
--num_threads=$num_threads \
--total_steps=${3} \
--log_steps=${4} \
--batch_size=${5} \
--data_path=${6} \
--output_path=${7} \
--no_horovod=${8} \
--learning_rate=${9} \
--s3_endpoint=${10} \
--s3_verify_ssl=${11} \
--s3_use_https=${12} \
--aws_access_key_id=${13} \
--aws_secret_access_key=${14} \
--aws_region=${15}
