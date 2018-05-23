#! /bin/bash

# install ksonnet + kubeflow so we can support TFJob

NAMESPACE=kubeflow
VERSION=3920d1402f40455c0f3e5f54ea4cc8142c23c2c8
APP_NAME=kubeflow
# by default we'll use our hyperkube config
# TODO: delete the hyperkube config
# : "${KUBECONFIG:=../resources/config.yaml}"
# workaround for https://github.com/ksonnet/ksonnet/issues/298
export USER=root

# pull ksonnet from web
curl -LO https://github.com/ksonnet/ksonnet/releases/download/v0.9.2/ks_0.9.2_linux_amd64.tar.gz
tar -xvf ks_0.9.2_linux_amd64.tar.gz
sudo mv ./ks_0.9.2_linux_amd64/ks /usr/local/bin/ks

# create namespace if doesn't exist yet
kubectl create namespace $NAMESPACE -v=7 || true

# create basic ks app
cd /tmp
ks init $APP_NAME
cd $APP_NAME
ks env set default --namespace $NAMESPACE

# install kubeflow components for TFJob support
ks registry add kubeflow github.com/kubeflow/kubeflow/tree/$VERSION/kubeflow
ks pkg install kubeflow/core@$VERSION
ks pkg install kubeflow/tf-job@$VERSION
ks pkg install kubeflow/pytorch-job@$VERSION
ks generate kubeflow-core kubeflow-core
ks generate pytorch-operator pytorch-operator
ks apply default -c kubeflow-core
ks apply default -c pytorch-operator
