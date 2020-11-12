#!/bin/bash 

if [[ "$1" = "-h" ]]; then 
  echo "Usage: $0 <music folder path>"
  echo "Will source .env, as docker-compose"
  exit 0
fi 

export $(cat .env | xargs)
export BEATPLAYER_MUSIC_FOLDER=${1:=}
export BEATPLAYER_SKIP_MOUNT_CHECK=1

pushd beatplayer 
./mpplayer.py -a 0.0.0.0 -p ${BEATPLAYER_PORT}
popd
