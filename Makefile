PACKAGE_NAME := freshbeats-app
SHELL := /bin/bash
INVENV := $(if $(VIRTUAL_ENV),1,0)
PYTHONINT := $(shell which python3)
PYTHON_VERSION := 3.11
WORKON_HOME := ~/.virtualenv
VENV_WRAPPER := /usr/share/virtualenvwrapper/virtualenvwrapper.sh
#LATEST_VERSION := $(shell git tag | grep -E "^v[[:digit:]]+.[[:digit:]]+.[[:digit:]]+$$" | sort -n | tail -n 1)
BRANCH := $(shell git branch --show-current)
DRY_RUN_PARAM := $(if $(DRY_RUN),--dry-run,)

API_CHANGES := $(strip $(shell git status -s -- src/points-api | wc -l))
API_HEAD_VERSION_TAG := $(shell git tag --contains | head -n 1 | grep -E "^$(PACKAGE_NAME)-api-v[[:digit:]]+.[[:digit:]]+.[[:digit:]]+$$")
API_HEAD_TAGGED := $(if $(API_HEAD_VERSION_TAG),1,0)

PROJECT_BASE := webapp
UI_CMD := ./manage.py runserver 0.0.0.0:8010
DBSHELL_CMD := ./manage.py dbshell 
PROJECTS_PATH := ../../projects 
GITHUB_PATH := ..

FRESHBEATS_APP_ENV := $(shell cat $(PROJECT_BASE)/dev.env | xargs)

UI_CHANGES := $(strip $(shell git status -s -- $(PROJECT_BASE) | wc -l))
UI_HEAD_VERSION_TAG := $(shell git tag --contains | head -n 1 | grep -E "^$(PACKAGE_NAME)-ui-v[[:digit:]]+.[[:digit:]]+.[[:digit:]]+$$")
UI_HEAD_TAGGED := $(if $(UI_HEAD_VERSION_TAG),1,0)

export DOCKER_REGISTRY := $(DOCKER_REGISTRY)/
ENV ?= dev
NOCACHE := # --no-cache

# # general environment 
# include env/${ENV}.env 
# export $(shell sed 's/=.*//' env/${ENV}.env)

# # API environment 
# include src/points-api/env/${ENV}.env 
# export $(shell sed 's/=.*//' src/points-api/env/${ENV}.env)

# # UI environment 
# include $(PROJECT_BASE)/env/${ENV}.env 
# export $(shell sed 's/=.*//' $(PROJECT_BASE)/env/${ENV}.env)

mysql = mysql -u ${DB_USER} -h ${DB_HOST} ${DB_DATABASE} -p${DB_PASSWORD}
execute = python -m jroutes.serve -r api

define build_and_up
	docker-compose build $(NOCACHE) $(1)
	docker-compose up --no-build --force-recreate -d $(1) 
endef 

define down
	docker-compose down $(1)
endef

define shell_into
	docker-compose exec $(PACKAGE_NAME)_$(1)_${ENV} /bin/bash 
endef 

define version 
	pushd $(1) \
		&& standard-version \
			$(DRY_RUN_PARAM) \
			--preMajor true \
			--releaseCommitMessageFormat="release($(2)) {{currentTag}}" \
			-a \
			--path ./ \
			--header "# $(2) Changelog" \
			--tag-prefix $(2)-v
endef 

### 

venv-reset:
	. $(VENV_WRAPPER) \
		&& rmvirtualenv $(PACKAGE_NAME)

dev-reset: venv-reset

venv:	
	. $(VENV_WRAPPER) \
		&& (workon $(PACKAGE_NAME) 2>/dev/null || mkvirtualenv -a . -p $(PYTHONINT) $(PACKAGE_NAME))
	. $(VENV_WRAPPER) \
		&& workon $(PACKAGE_NAME) \
		&& pip install --upgrade pip
	. $(VENV_WRAPPER) \
		&& workon $(PACKAGE_NAME) \
		&& pip install \
			--extra-index-url https://test.pypi.org/simple \
			-t $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages \
			-r $(PROJECT_BASE)/requirements.txt

vendor-install:
	ln -svf $(PWD)/$(PROJECTS_PATH)/frank-common/src/frank $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages/
	ln -svf $(PWD)/$(GITHUB_PATH)/jroutes/src/jroutes $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages/
	ln -svf $(PWD)/$(GITHUB_PATH)/cowpy/src/cowpy $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages/

dev-setup-api: venv vendor-install 

runtabs:
	xfce4-terminal --working-directory=${PWD} --tab 
	xfce4-terminal --working-directory=${PWD}/services/switchboard --tab 

runwindows:
	xfce4-terminal --working-directory=${PWD}/services/beatplayer --color-bg=green 
	xfce4-terminal --working-directory=${PWD} --color-bg=blue 

logwindows:
	xfce4-terminal --working-directory=${PWD}/services/beatplayer --color-bg=green # health 
	xfce4-terminal --working-directory=${PWD}/services/beatplayer --color-bg=green # socket 
	xfce4-terminal --working-directory=${PWD}/services/beatplayer --color-bg=green # action 
	xfce4-terminal --working-directory=${PWD}/services/beatplayer --color-bg=green # exception
	xfce4-terminal --working-directory=${PWD}/webapp --color-bg=blue # health (beatplayer)
	xfce4-terminal --working-directory=${PWD}/webapp --color-bg=blue # health registration 
	xfce4-terminal --working-directory=${PWD}/webapp --color-bg=blue # action 

windows: runtabs runwindows logwindows

devrun_ui:
	(. $(VENV_WRAPPER) \
		&& workon $(PACKAGE_NAME) \
		&& pushd $(PROJECT_BASE) \
		&& $(FRESHBEATS_APP_ENV) $(UI_CMD)) \
		|| echo "Make sure to: make dev-setup-api!"

sql:
	(. $(VENV_WRAPPER) \
		&& workon $(PACKAGE_NAME) \
		&& pushd $(PROJECT_BASE) \
		&& $(FRESHBEATS_APP_ENV) $(DBSHELL_CMD)) \
		|| echo "Make sure to: make dev-setup-api!"

test:
	@echo "not implemented!"

version_api:
ifeq ($(BRANCH), main)
ifeq ($(API_CHANGES), 0)
ifeq ($(API_HEAD_TAGGED), 0)
	@echo "Versioning $* (DRY_RUN=$(DRY_RUN))"
# ifneq ($(DRY_RUN), 1)
	pushd src/points-api \
		&& sed -i \
			"s/^version = .*/version = \"$(shell standard-version --dry-run -a --path ./ --tag-prefix $(PACKAGE_NAME)-api-v  | grep "tagging release" | awk '{ print $$4 }')\"/" \
			pyproject.toml \
		&& git diff -- pyproject.toml \
		&& git add pyproject.toml
	$(call version,src/points-api,$(PACKAGE_NAME)-api)
else # head tagged 
	@echo "No versioning today (commit already tagged $(API_HEAD_VERSION_TAG))"	
endif # head not tagged 
else # changes 
	@echo "No versioning today (%=$* BRANCH=$(BRANCH) CHANGES=$(API_CHANGES) HEAD_VERSION_TAG=$(API_HEAD_VERSION_TAG) HEAD_TAGGED=$(API_HEAD_TAGGED) DRY_RUN_PARAM=$(DRY_RUN_PARAM)). Stash or commit your changes."
	exit 1
endif # no changes 
else # not on main 
	@echo "Will not version outside main"
	exit 1
endif # on main 

version_ui:
ifeq ($(BRANCH), main)
ifeq ($(UI_CHANGES), 0)
ifeq ($(UI_HEAD_TAGGED), 0)
	@echo "Versioning $* (DRY_RUN=$(DRY_RUN))"
# ifneq ($(DRY_RUN), 1)
	$(call version,$(PROJECT_BASE),$(PACKAGE_NAME)-ui)
else # head tagged 
	@echo "No versioning today (commit already tagged $(UI_HEAD_VERSION_TAG))"	
endif # head not tagged 
else # changes 
	@echo "No versioning today (%=$* BRANCH=$(BRANCH) CHANGES=$(UI_CHANGES) HEAD_VERSION_TAG=$(UI_HEAD_VERSION_TAG) HEAD_TAGGED=$(UI_HEAD_TAGGED) DRY_RUN_PARAM=$(DRY_RUN_PARAM)). Stash or commit your changes."
	exit 1
endif # no changes 
else # not on main 
	@echo "Will not version outside main"
	exit 1
endif # on main 

vendor-refresh:
	rm -rf src/points-api/vendor && mkdir src/points-api/vendor \
		&& cp -R $(PWD)/$(PROJECTS_PATH)/frank-common src/points-api/vendor/ \
		&& cp -R $(PWD)/$(GITHUB_PATH)/jroutes src/points-api/vendor/ \
		&& cp -R $(PWD)/$(GITHUB_PATH)/cowpy src/points-api/vendor/

deploy_api: vendor-refresh 
	$(call build_and_up,$(PACKAGE_NAME)_api_${ENV})

deploy_ui: 
	$(call build_and_up,$(PACKAGE_NAME)_ui_${ENV})

deploy: deploy_api deploy_ui

shell_api:
	$(call shell_into,api)

shell_ui:
	$(call shell_into,ui)

logs:
	docker-compose logs -f

teardown_api: 
	$(call down,$(PACKAGE_NAME)_api_${ENV})

teardown_ui: 
	$(call down,$(PACKAGE_NAME)_ui_${ENV})

teardown: teardown_ui teardown_api

.PHONY: restoredb
restoredb:
	@echo "dumping"
	$(shell mysqldump $(PACKAGE_NAME) | mysql $(PACKAGE_NAME)_dev)

makemigration:
	PATH_TO_DB=$(PWD)/src/points-api MIGRATIONS_FOLDER=$(PWD)/src/points-api/migrations dbdt new 

migration:
	PATH_TO_DB=$(PWD).. oh wait dbup-downtown doesn't support mysql (yet)

clean:
	find src/points-api -type d -name __pycache__ | xargs rm -rvf 
	find src/points-api -type f -name *.pyc | xargs rm -vf 
