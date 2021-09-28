#!/bin/bash 

if [[ "$1" = "-h" ]]; then 
  echo "Usage: $0 <music folder path>"
  echo "Will source .env, as docker-compose"
  exit 0
fi 

export $(cat .env | xargs)

if [[ $# -gt 0 ]]; then 
  BEATPLAYER_MUSIC_FOLDER=$1
fi 

export BEATPLAYER_MUSIC_FOLDER=${BEATPLAYER_MUSIC_FOLDER:=${HOST_MUSIC_FOLDER}}
export BEATPLAYER_SKIP_MOUNT_CHECK=1

env | grep BEATPLAYER

pushd beatplayer 
./mpplayer.py -a 0.0.0.0 -p ${BEATPLAYER_PORT}
popd
