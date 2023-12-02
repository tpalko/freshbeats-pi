#!/bin/bash 

CMD=runserver 
HOST_ADDRESS=0.0.0.0
HOST_PORT=8010
HOST=${HOST_ADDRESS}:${HOST_PORT}

while [[ $# -gt 0 ]]; do 
  echo "$# args"
  case $1 in
    -c) CMD=$2; shift; shift;;
    -h) HOST=$2; shift; shift;;
    --) shift; break;;
    *) echo "Don't know $1" && exit 1;;
  esac
done 

[[ "${CMD}" != "runserver" ]] && echo "Clearing HOST" && HOST=

export $(cat dev.env | xargs)

echo "${CMD} : ${HOST}"
mkdir -p ./log

if [[ "${CMD}" = "runserver" ]]; then 
  python manage.py ${CMD} ${HOST} $@ 2>&1 | tee -a ./log/$0_$(date +%Y%m%dT%H%M%S).log
else 
  python manage.py ${CMD} $@
fi 
