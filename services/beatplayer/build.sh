#!/bin/bash 

function usage() {
  echo "Purpose: A script to build a beatplayer image with an appropriate base architecture for the system on which it's called."
  echo "i.e. run this script on the deploy target architecture"
  echo "Usage: $0 [DOCKER_REGISTRY]"
}

[[ "$1" = "-h" ]] && usage && exit 0

DOCKER_REGISTRY=$1
CPU_ARCH=${CPU_ARCH:=$(uname -m)}

case ${CPU_ARCH} in 
  armv6l)    ALPINE_ARCH=arm32v6;;
  armv7l)    ALPINE_ARCH=arm32v7;;
  x86_64|*)  ALPINE_ARCH=amd64;;  
esac 

echo "CPU_ARCH: ${CPU_ARCH}"
echo "ALPINE_ARCH: ${ALPINE_ARCH}"

docker build -t beatplayer:${CPU_ARCH} --build-arg ALPINE_ARCH=${ALPINE_ARCH} .
BUILD_RETURN=$?

[[ "${BUILD_RETURN}" -eq 0 && -n "${DOCKER_REGISTRY}" ]] \
 && docker tag beatplayer:${CPU_ARCH} ${DOCKER_REGISTRY}/beatplayer:${CPU_ARCH} \
 && docker push ${DOCKER_REGISTRY}/beatplayer:${CPU_ARCH}
