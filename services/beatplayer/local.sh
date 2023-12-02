#!/bin/bash 

function usage() {
  echo "Usage: $0 [ optional <music folder path> ]"
  echo "Will source .env, as docker-compose"
}

if [[ "$1" = "-h" ]]; then 
  usage   
  exit 0
fi 

export $(cat .env | xargs)

env | grep BEATPLAYER

# pushd beatplayer 

case $1 in 
  http)  gunicorn -b 0.0.0.0:9000 server.serving:handler
          ;;
  rpc)    python -m beatplayer.mpplayer 
          ;;
  *)      usage; exit 1
          ;;
esac 

# popd 