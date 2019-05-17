<div>
<h1>
<img src="docs/warning.png"/>
Deprecation notice
</h1>

Intel is winding down development and maintenance of MLT.

Please see [Nauta](www.intel.ai/nauta), [Deep Learning Reference Stack](https://clearlinux.org/stacks/deep-learning-reference-stack) or [Kubeflow](www.kubeflow.org) for coverage of end to end data science workflows.
</div>


# mlt
Machine Learning Container Templates

> MLT: it's like the keras of kubernetes
>
> \- @mas-dse-greina

[![CircleCI](https://circleci.com/gh/IntelAI/mlt.svg?style=svg&circle-token=239cc4305ca25063bf9a40cd332c822f5e64663f)](https://circleci.com/gh/IntelAI/mlt)

`mlt` aids in the creation of containers for machine learning jobs.
It does so by making it easy to use container and kubernetes object templates.

![MLT flow diagram](docs/mlt.png)

We have found it useful to share project templates for various machine learning frameworks. Some have native support from Kubernetes operators, such as mxnet and TensorFlow. Others do not, but still have best practices for how to run on a Kubernetes cluster.

On top of getting boiler plate code at the beginning of a project to work, the best practices may change over time. `mlt` allows existing projects to adapt to these without having to reset and start over.

![MLT watch](docs/watch.png)

`mlt` addresses another aspect of the application development: _iterative_ container creation. Storage and container creation is supposed to be fast - so why not rebuild containers automatically?
`mlt` has a `--watch` option, which lets you write code and have an IDE-like experience.
When changes are detected, a timer starts and triggers container rebuilds.
lint and unit tests can be run in this step, as an early indicator of whether the code will run in the cluster.
When the container is built, it is pushed to the cluster container registry.
From here, it is a quick step to redeploy the Kubernetes objects, through `mlt deploy`


## Build

Prerequisites:
- Python (2.7 or newer) development environment. This usually consists of `build-essential`, `libssl-dev`, `libffi-dev` and `python-dev`
- [Docker](https://docs.docker.com/install/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
- [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- [python](https://www.python.org/downloads/)
- [pip](https://pip.pypa.io/en/stable/installing/)

Optional prerequisites:
- [kubetail](https://github.com/johanhaleby/kubetail) (for `mlt logs` command)
- [Ksync](https://github.com/vapor-ware/ksync) (for `mlt sync` commands)
- [ks](https://github.com/IntelAI/mlt/blob/master/scripts/ksonnet_install_linux.sh) (Needed `0.11.0` version for volume support to work in `horovod` template)
- [TFJob operator](https://github.com/kubeflow/tf-operator#installing-the-tfjob-crd-and-operator-on-your-k8s-cluster) (for the `distributed tensorflow` templates)
- [PyTorch operator](https://github.com/kubeflow/pytorch-operator) (for the `pytorch-distributed` template)
- [jq](http://macappstore.org/jq/) (for the `tensorboard` templates)
- [openssh-server](https://www.openssh.com/) (for the `horovod` template)

Linux Debian-based distro users:
- Run `make debian_prereq_install` to install every dependency required for `mlt` to work. We assume users already have `kubectl` and `docker` set up though.

## Installation

### Install from [PyPI](https://pypi.org/)
```bash
$ pip install mlt
```

### Installation from Source

```bash
$ git clone git@github.com:IntelAI/mlt.git
Cloning into 'mlt'...
remote: Counting objects: 1981, done.
remote: Compressing objects: 100% (202/202), done.
remote: Total 1981 (delta 202), reused 280 (delta 121), pack-reused 1599
Receiving objects: 100% (1981/1981), 438.10 KiB | 6.54 MiB/s, done.
Resolving deltas: 100% (1078/1078), done.

$ cd mlt

$ pip install .
```

## Create local Python distributions
```bash
$ make dist
$ cd dist
$ ls mlt*
mlt-0.1.0a1+12.gf49c412.dirty-py2.py3-none-any.whl
```

## Usage summary

### Sample mlt deployment
[![asciicast](https://asciinema.org/a/171353.png)](https://asciinema.org/a/171353)

```bash

$ mlt template list

Template             Description
-------------------  --------------------------------------------------------------------------------------------------
hello-world          A TensorFlow python HelloWorld example run through Kubernetes Jobs.
pytorch              Sample distributed application taken from http://pytorch.org/tutorials/intermediate/dist_tuto.html
pytorch-distributed  A distributed PyTorch MNIST example run using the pytorch-operator.
tf-dist-mnist        A distributed TensorFlow MNIST model which designates worker 0 as the chief.
tf-distributed       A distributed TensorFlow matrix multiplication run through the TensorFlow Kubernetes Operator.

$ mlt init my-app --template=hello-world
[master (root-commit) 40239a2] Initial commit.
 7 files changed, 191 insertions(+)
 create mode 100644 mlt.json
 create mode 100644 Dockerfile
 create mode 100644 Makefile
 create mode 100644 k8s-templates/tfjob.yaml
 create mode 100644 k8s/README.md
 create mode 100644 main.py
 create mode 100644 requirements.txt

$ cd my-app

# NOTE: `mlt config` has been renamed to `mlt template_config` to avoid confusion regarding developer config settings.

# List template-specific config parameters
$ mlt template_config list
Parameter Name                Value
----------------------------  ----------------------
registry                      my-project-12345
namespace                     my-app
name                          my-app
template_parameters.greeting  Hello

# Update the greeting parameter
$ mlt template_config set template_parameters.greeting Hi

# Check the template_config list to see the updated parameter value
$ mlt template_config list
Parameter Name                Value
----------------------------  ----------------------
registry                      constant-cubist-173123
namespace                     dmsuehir
name                          dmsuehir
template_parameters.greeting  Hi

$ mlt build
Starting build my-app:71fb176d-28a9-46c2-ab51-fe3d4a88b02c
Building |######################################################| (ETA:  0:00:00)
Pushing  |######################################################| (ETA:  0:00:00)
Built and pushed to gcr.io/my-project-12345/my-app:71fb176d-28a9-46c2-ab51-fe3d4a88b02c

$ mlt deploy
Deploying gcr.io/my-project-12345/my-app:71fb176d-28a9-46c2-ab51-fe3d4a88b02c

Inspect created objects by running:
  $ kubectl get --namespace=my-app all

### Provide -l flag to tail logs immediately after deploying.
$ mlt deploy --no-push -l
Skipping image push
Deploying gcr.io/my-project-12345/my-app:b9f124d2-ef34-4d66-b137-b8a6026bf782

Inspect created objects by running:
$ kubectl get --namespace=my-app all

Checking for pod(s) readiness
Will tail 1 logs...
my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg
[my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg] 2018-05-17 22:28:34.578791: I tensorflow/core/platform/cpu_feature_guard.cc:140] Your CPU supports instructions that this TensorFlow binary was not compiled to use: AVX2 AVX512F FMA
[my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg] b'Hello, TensorFlow!'

$ mlt status
NAME                                                  READY     STATUS    RESTARTS   AGE       IP            NODE
my-app-897cb68f-e91f-42a0-968e-3e8073334450-vvpqj     1/1       Running   0          14s       10.23.45.67   gke-my-cluster-highmem-8-skylake-1

### To deploy in interactive mode (using no-push as an example)
### NOTE: only basic functionality is supported at this time. Only one container and one pod in a deployment for now.
#### If more than one container in a deployment, we'll pick the first one we find and deploy that.

$ mlt deploy -i --no-push
Skipping image push
Deploying localhost:5000/test:d6c9c06b-2b64-4038-a6a9-434bf90d6acc

$ mlt logs
Checking for pod(s) readiness
Will tail 1 logs...
my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg
[my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg] 2018-05-17 22:28:34.578791: I tensorflow/core/platform/cpu_feature_guard.cc:140] Your CPU supports instructions that this TensorFlow binary was not compiled to use: AVX2 AVX512F FMA
[my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg] b'Hello, TensorFlow!'

Inspect created objects by running:
$ kubectl get --namespace=my-app all

Connecting to pod...
root@test-9e035719-1d8b-4e0c-adcb-f706429ffeac-wl42v:/src/app# ls
Dockerfile  Makefile  README.md  k8s  k8s-templates  main.py  mlt.json	requirements.txt

# Displays events for the current job
$ mlt events
LAST SEEN   FIRST SEEN   COUNT     NAME                                                                            KIND      SUBOBJECT                     TYPE      REASON                  SOURCE                                                   MESSAGE

6m          6m           1         my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg.152f8f13466696b4              Pod                                     Normal    Scheduled               default-scheduler                                        Successfully assigned my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg to gke-dls-us-n1-highmem-8-skylake-82af83b4-8nvh
6m          6m           1         my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg.152f8f134ff373d7              Pod                                     Normal    SuccessfulMountVolume   kubelet, gke-dls-us-n1-highmem-8-skylake-82af83b4-8nvh   MountVolume.SetUp succeeded for volume "default-token-grq2c"
6m          6m           1         my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg.152f8f1399b33ba0              Pod       spec.containers{my-app}       Normal    Pulled                  kubelet, gke-dls-us-n1-highmem-8-skylake-82af83b4-8nvh   Container image "gcr.io/my-project-12345/my-app:b9f124d2-ef34-4d66-b137-b8a6026bf782" already present on machine
6m          6m           1         my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg.152f8f139dec0dc3              Pod       spec.containers{my-app}       Normal    Created                 kubelet, gke-dls-us-n1-highmem-8-skylake-82af83b4-8nvh   Created container
6m          6m           1         my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg.152f8f13a2ea0ff6              Pod       spec.containers{my-app}       Normal    Started                 kubelet, gke-dls-us-n1-highmem-8-skylake-82af83b4-8nvh   Started container
6m          6m           1         my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33.152f8f13461279e4                    Job                                     Normal    SuccessfulCreate        job-controller                                           Created pod: my-app-09aa35f4-bdf8-4da8-8400-8728bf7afa33-sqzqg


```

### Examples

* [Distributed U-Net model training using KVC and MLT](examples/distributed_unet)
* [Distributed U-Net model training using horovod and openmpi on Kubernetes](examples/horovod_unet)

### Template Development

To add new templates, see the [Template Developers Manual](docs/template_developers.md).
