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

SHELL=bash
PY := $(shell python --version 2>&1  | cut -c8)
VIRTUALENV_DIR=$(if $(subst 2,,$(PY)),.venv3,.venv)
ACTIVATE="$(VIRTUALENV_DIR)/bin/activate"

.PHONY: venv test lint clean

all: venv

venv:
	@echo "Creating python2 and 3 virtualenv in .venv and .venv3 dirs"
	@tox -e py2-venv -e py3-venv

dev-env:
	@echo "Creating python2 and 3 editable install in .venv and .venv3"
	@tox -e py2-dev -e py3-dev

test:
	@echo "Running unit tests across python platforms..."
	@tox -e py2-unit -e py3-unit

lint:
	@echo "Linting with flake8..."
	@tox -e py2-lint -e py3-lint

coverage:
	@echo "Running coverage report..."
	@tox -e py2-coverage -e py3-coverage

install:
	@echo "Installing mlt to system..."
	@python${PY} setup.py install

uninstall:
	@echo "Uninstalling mlt from system..."
	@pip${PY} uninstall -y mlt

docker:
	docker build \
        --build-arg HTTP_PROXY=${HTTP_PROXY} \
        --build-arg HTTPS_PROXY=${HTTPS_PROXY} \
        --build-arg NO_PROXY=${NO_PROXY} \
        --build-arg http_proxy=${http_proxy} \
        --build-arg https_proxy=${https_proxy} \
        --build-arg no_proxy=${no_proxy} \
        -t mlt .

env-up: docker
	docker-compose up -d

env-down:
	docker-compose down

env-reset: env-down env-up


# kubeflow is needed for the TFJob and PytorchJob operators (our templates use this)
# we get the mltkey.json from the circleci setup
# we then need to alias our gcloud setup to just `gcloud` for mlt
test-e2e: env-up
	docker-compose exec test pip install tox
	docker cp /home/circleci/.kube/config mlt:/root/.gcloudkube/config
	docker-compose exec test sed -i "s/cmd-path: \/home\/circleci\/repo\/google-cloud-sdk/cmd-path: \/usr\/share\/mlt\/google-cloud-sdk/" /root/.gcloudkube/config
	docker-compose exec test bash -c "docker login -u _json_key --password-stdin https://gcr.io < mltkey.json"
	docker-compose exec test bash -c "./google-cloud-sdk/bin/gcloud auth activate-service-account mltjson@intelai-mlt.iam.gserviceaccount.com --key-file=mltkey.json"
	docker-compose exec test bash -c "ln -s /usr/share/mlt/google-cloud-sdk/bin/gcloud /usr/local/bin/gcloud"
	docker-compose exec test env MLT_REGISTRY=gcr.io/intelai-mlt tox -e py2-e2e -e py3-e2e

# EXTRA_ARGS enables usage of other docker registries for testing
# ex: EXTRA_ARGS=`$MLT_REGISTRY_AUTH_COMMAND` make test-e2e-no-docker
# if you'd like to use something other than localhost:5000, also set
# MLT_REGISTRY env var and that'll be respected by tox
test-e2e-no-docker:
	@[ `kubectl get crd | grep -E 'tfjobs\.kubeflow\.org|pytorchjobs\.kubeflow\.org' -c` -eq "2" ] || \
		GITHUB_TOKEN=${GITHUB_TOKEN} ./scripts/kubeflow_install.sh
	@${EXTRA_ARGS:} tox -e py2-e2e -e py3-e2e

clean:
	rm -rf .venv .venv3
	find . -name '*.pyc' -delete

dist: venv
	@echo "Building wheels for distribution..."
	@echo "Virtual env dir is ${VIRTUALENV_DIR}"
	@. $(ACTIVATE); pip wheel --wheel-dir=dist -r requirements.txt .

release: dist
	if [ -r ~/.pypirc ]; then \
		echo "Uploading to PyPI..." ; \
		. $(ACTIVATE); twine upload dist/mlt* ; \
	else \
		echo "~/.pypirc not found" ; \
	fi;
