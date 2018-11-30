# Distributed TensorFlow using Horovod

A distributed model training using horovod and openmpi with added support for S3 storage.

This template deploys horovod model on kubernetes using [kubeflow openmpi](https://github.com/kubeflow/kubeflow/blob/master/kubeflow/openmpi/README.md).

Template structure as follows:

* [Dockerfile.cpu](Dockerfile.cpu) - Installs required packages.
* [deploy.sh](deploy.sh) - Custom deployment file which uses kubeflow/openmpi component instructions to deploy on to kubernetes
* [exec_multiworker.sh](exec_multiworker.sh) - Entry point in deploy.sh file which initiates the training
* [main.py](main.py) - Model file
* [parameters.json](parameters.json) - Extra template parameters
* [requirements.txt](requirements.txt) - Extra python packages

## Volume support

We have volume support in our template where you can mount `hostpath` on your kubernetes node as volume inside containers.
We have used [vck](https://github.com/IntelAI/vck/blob/master/docs/ops.md#installing-the-controller) to  transfer data to kubernetes cluster.

Please update below paths in `mlt.json`(this file will be created after `mlt init`)
* `data_path` - Path to training data (.npy files in our case)

  * Can be updated with the command

    `mlt template_config set template_parameters.data_path << hostpath >>`

* `output_path` - Sub-directory inside the mounted volume to store results. You can use this path to check your results after training finishes.

  * Can be updated with the command

    `mlt template_config set template_parameters.output_path << hostpath >>`

In case of this `mnist` example, data will be downloaded inside containers if provided path is not valid.

## S3 object store support

You will need to set S3 configuration parameters by editing the mlt.json file or running the following commands
```
mlt template_config set template_parameters.s3_endpoint << endpoint IP:Port >>
mlt template_config set template_parameters.s3_verify_ssl 0 (0 or 1)
mlt template_config set template_parameters.s3_use_https 0 (0 or 1)
mlt template_config set template_parameters.aws_access_key_id << aws access key id >>
mlt template_config set template_parameters.aws_secret_access_key << aws access secret >>
mlt template_config set template_parameters.aws_region << aws region for S3 or Local >>
mlt template_config set template_parameters.data_path s3://<< bucket name >>/<< folder path >>
mlt template_config set template_parameters.output_path s3://<< bucket name >>/<< folder path >>
```
