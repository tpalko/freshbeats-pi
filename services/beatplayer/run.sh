#!/bin/bash 

function usage() {
  echo "Purpose: A script to run beatplayer with an appropriate base architecture image for the system on which it's called."
  echo "Usage: $0 [DOCKER_REGISTRY] -- [additional docker-compose up flags]"
}

[[ "$1" = "-h" ]] && usage && exit 0

export ARCH=$(uname -m)

while [[ $# -gt 0 ]]; do 
  case $1 in
    --) shift; break;;
    -r) export DOCKER_REGISTRY=$2/; shift; shift;;
  esac 
done 

docker-compose up $@
