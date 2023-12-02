PACKAGE_NAME := freshbeats-beatplayer
SHELL := /bin/bash
INVENV := $(if $(VIRTUAL_ENV),1,0)
PYTHONINT := $(shell which python3)
PYTHON_VERSION := 3.11
WORKON_HOME := ~/.virtualenv
VENV_WRAPPER := /usr/share/virtualenvwrapper/virtualenvwrapper.sh
export PORT ?= 9000
export SERVER_ROUTE_MODULES ?= beatplayer.routes 
BEATPLAYER_ENV := $(shell cat .env | xargs)

serve = python -m jroutes.serve -r beatplayer.routes -p 9000

venv-reset:
	. $(VENV_WRAPPER) \
		&& rmvirtualenv $(PACKAGE_NAME)

dev-reset: venv-reset

venv:	
	. $(VENV_WRAPPER) \
		&& (workon $(PACKAGE_NAME) 2>/dev/null || mkvirtualenv -a . -p $(PYTHONINT) $(PACKAGE_NAME)) \
		&& pip install --upgrade pip \
		&& pip install \
			--extra-index-url https://test.pypi.org/simple \
			-t $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages \
			-r requirements.txt

vendor-install:
	ln -sf ${PWD}/../../../jroutes/src/jroutes $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages/
	ln -sf ${PWD}/../../../cowpy/src/cowpy $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages/

dev-setup-api: venv vendor-install 

devrun_api:
	@(. $(VENV_WRAPPER) \
		&& workon $(PACKAGE_NAME) \
		&& $(BEATPLAYER_ENV) $(call serve)) \
		|| echo "Make sure to: make dev-setup-api!"

vendor:
	mkdir -p vendor
	rm -rf vendor/cowpy
	cp -anv ${PWD}/../../../cowpy vendor/cowpy

build: vendor
	docker-compose build

push: build 
	docker-compose push
