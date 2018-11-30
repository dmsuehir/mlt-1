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

# install ksonnet + kubeflow openmpi so we can support Horovod distributed training

VERSION=master
SECRET=openmpi-secret

# https://github.com/ksonnet/ksonnet/issues/298
export USER=root

# set your GITHUB_TOKEN otherwise deployment will fail with API Limit error
export GITHUB_TOKEN=$GITHUB_TOKEN

{
# Generate one-time ssh keys used by Open MPI.
SECRET=openmpi-secret
mkdir -p .tmp
echo "y" | ssh-keygen -N "" -f .tmp/id_rsa
kubectl delete secret ${SECRET} -n ${NAMESPACE} || true
kubectl create secret generic ${SECRET} -n ${NAMESPACE} --from-file=id_rsa=.tmp/id_rsa --from-file=id_rsa.pub=.tmp/id_rsa.pub --from-file=authorized_keys=.tmp/id_rsa.pub
rm -rf .tmp

# Initialize a ksonnet app. Set the namespace for it's default environment.
if [ -d "$JOB_NAME" ]; then
  pushd .
  cd ${JOB_NAME}
  set +e
  ks delete default
  ks component rm ${JOB_NAME}
  set -e
  popd
  rm -rf ${JOB_NAME}
fi

ks init ${JOB_NAME}
cd ${JOB_NAME}
ks env set default --namespace ${NAMESPACE}

# Install openmpi kubeflow component.
ks registry add kubeflow github.com/kubeflow/kubeflow/tree/${VERSION}/kubeflow
ks pkg install kubeflow/openmpi@${VERSION}

# Temporary fix for volume-mount
# Untill this is merged : https://github.com/kubeflow/kubeflow/issues/838
cp -rf ../volume-mount/workloads.libsonnet vendor/kubeflow/openmpi/
cp -rf ../volume-mount/prototypes/openmpi.jsonnet vendor/kubeflow/openmpi/prototypes/

# Generate openmpi components.

# Node selector helps to launch job on specific set of nodes with label.
# For kubernetes nodes we assigned label called `node-type=highmem` to set of nodes.
# Ex: kubectl label node gke-node-1 node-type=highmem
COMPONENT=${JOB_NAME}
IMAGE=${IMAGE}
WORKERS=$(( ${NUM_NODES} * ${NUM_WORKERS_PER_NODE} ))
GPU=${GPUS}
NODE_SELECTOR=${NODE_SELECTOR}
MEMORY=${MEMORY}

NUM_INTER_THREADS=${NUM_INTER_THREADS}
SOCKETS_PER_NODE=${SOCKETS_PER_NODE}
NUM_WORKERS_PER_NODE=${NUM_WORKERS_PER_NODE}
PHYSICAL_CORES=${PHYSICAL_CORES}
TOTAL_STEPS=${TOTAL_STEPS}
LOG_STEPS=${LOG_STEPS}
BATCH_SIZE=${BATCH_SIZE}
DATA_PATH=${DATA_PATH} # data path for training data
OUTPUT_PATH=${OUTPUT_PATH} # output path to store results
NO_HOROVOD=${NO_HOROVOD}
LEARNING_RATE=${LEARNING_RATE}
PPR=$(( $NUM_WORKERS_PER_NODE / $SOCKETS_PER_NODE ))

# S3 storage support configuration
S3_ENDPOINT=${S3_ENDPOINT}
S3_VERIFY_SSL=${S3_VERIFY_SSL}
S3_USE_HTTPS=${S3_USE_HTTPS}
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
AWS_REGION=${AWS_REGION}

EXEC="mpirun -np ${WORKERS} \
--hostfile /kubeflow/openmpi/assets/hostfile \
--map-by socket \
-cpus-per-proc ${PHYSICAL_CORES} \
--report-bindings \
--oversubscribe bash /src/app/exec_multiworker.sh \
${PPR} ${NUM_INTER_THREADS} ${TOTAL_STEPS} ${LOG_STEPS} \
${BATCH_SIZE} ${DATA_PATH} ${OUTPUT_PATH} ${NO_HOROVOD} \
${LEARNING_RATE} ${S3_ENDPOINT} ${S3_VERIFY_SSL} \
${S3_USE_HTTPS} ${AWS_ACCESS_KEY_ID} \
${AWS_SECRET_ACCESS_KEY} ${AWS_REGION}"

ks generate openmpi ${COMPONENT} \
--image ${IMAGE} \
--secret ${SECRET} \
--workers ${WORKERS} \
--gpu ${GPU} \
--exec "${EXEC}" #--nodeSelector ${NODE_SELECTOR} --memory ${MEMORY} # To set memory, uncomment.

} &> /dev/null

# If you have data on your host and you want to mount that as volume, please update data_path and output_path in mlt.json
# If you have data in a S3 object store, then set the s3_endpoint and other s3 values in mlt.json

if [ -z "${S3_ENDPOINT}" ]
    then
    # Lets make sure that the user was not trying to use S3
    # Check to see that the data path does not begine with s3:
    if [[ "${DATA_PATH:0:5}" == "s3://" ]]
        then
        echo "data_path starts with S3 but S3_ENDPOINT has not been set"
        exit
    fi
fi

# volumes - path in this section will create a volume for you based on host path provided
# volumeMounts - mountPath in this section will mount above volume at specified location
if [ -n "${DATA_PATH}" ] && [ ! -n "${S3_ENDPOINT}" ];
    then
        ks param set ${COMPONENT} volumes '[{ "name": "vol", "hostPath": { "path": "'"${DATA_PATH}"'"}}]'
        ks param set ${COMPONENT} volumeMounts '[{ "name": "vol", "mountPath": "'"${DATA_PATH}"'"}]'
fi

# Deploy to your cluster.
ks apply default
