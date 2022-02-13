#!/bin/bash 

CMD=runserver 
HOSTPORT=0.0.0.0:8000

while [[ $# -gt 0 ]]; do 
  case $1 in
    -c) CMD=$2; shift; shift;;
    -h) HOSTPORT=$2; shift; shift;;
  esac
done 

[[ "${CMD}" != "runserver" ]] && HOSTPORT=

echo "$(cat dev.env | xargs) python manage.py ${CMD} ${HOSTPORT} $@.."
env $(cat dev.env | xargs) python manage.py ${CMD} ${HOSTPORT} $@
