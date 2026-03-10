CONTAINER=genaigke-sample
MOCKED_APPLICATION_NAME=$CONTAINER
PYTHONCMD=python3
PYTHON36_FOUND=$(shell command -v python3.6 2>/dev/null)

AMBIENTE?=prod

ifeq ($(AMBIENTE),prod)
	PYTEST_UNIT_EXCLUDE :=
	PIP_INSTALL_FLAGS := --user
endif


ifeq ($(AMBIENTE),terceiros)
	PYTEST_UNIT_EXCLUDE := -m "not hbase"
	PIP_INSTALL_FLAGS :=
endif


ifndef PYTHON36_FOUND
	PYTHONCMD=python3
endif


compile: deps
	$(PYTHONCMD) -m compileall ./

lint: devdeps
	flake8 . || true


tests:
	exit 0 

unit-tests: devdeps delete-coverage-report
	$(PYTHONCMD) -m pytest -v --cov=./ --cov-report=html --cov-report=xml --cov-report=term $(PYTEST_UNIT_EXCLUDE) tests/unit

delete-coverage-report:
	rm -rf coverage-reports/

integration-tests:
	exit 0

deps: 
	$(PYTHONCMD) -m pip install $(PIP_INSTALL_FLAGS) -r requirements.txt
	pip3 install $(PIP_INSTALL_FLAGS) -r requirements.txt

devdeps:
	$(PYTHONCMD) -m pip install $(PIP_INSTALL_FLAGS) -r requirements-dev.txt
	pip3 install $(PIP_INSTALL_FLAGS) -r requirements-dev.txt

buildwheel:
	$(PYTHONCMD) setup.py bdist_wheel

clean: