#!/bin/bash 

#if [[ $# -gt 1 ]]; then export EXTRA=$1; shift; fi
EXTRA=
echo "$(cat dev.env | xargs) ${EXTRA} python manage.py $@.."
env $(cat dev.env | xargs) ${EXTRA} python manage.py $@
