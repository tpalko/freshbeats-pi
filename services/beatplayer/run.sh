#!/bin/bash 

function usage() {
  echo "Purpose: A script to run beatplayer with an appropriate base architecture image for the system on which it's called."
  echo "Usage: $0 [-r DOCKER_REGISTRY] -- [additional docker-compose up flags]"
}

[[ "$1" = "-h" ]] && usage && exit 0

# export HOST_MUSIC_FOLDER=/media/storage/music
export CPU_ARCH=$(uname -m)

case ${CPU_ARCH} in 
  armv6l)    ALPINE_ARCH=arm32v6;;
  armv7l)    ALPINE_ARCH=arm32v7;;
  x86_64|*)  ALPINE_ARCH=amd64;;  
esac 

export ALPINE_ARCH


# while [[ $# -gt 0 ]]; do 
#   case $1 in
#     --) shift; break;;
#     -r) export DOCKER_REGISTRY=$2/; shift; shift;;
#   esac 
# done 

env | grep BEATPLAYER

echo "docker-compose up $@"

docker-compose down && docker-compose up $@
