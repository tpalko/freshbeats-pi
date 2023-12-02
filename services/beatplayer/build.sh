#!/bin/bash 

function usage() {
  echo "Purpose: A script to build a beatplayer image with an appropriate base architecture for the system on which it's called."
  echo "i.e. run this script on the deploy target architecture"
  # echo "Usage: $0 [DOCKER_REGISTRY]"
}

# [[ "$1" = "-h" ]] && usage && exit 0

# DOCKER_REGISTRY=$1
export CPU_ARCH=${CPU_ARCH:=$(uname -m)}
# IMAGE_NAME=beatplayer:${CPU_ARCH}

case ${CPU_ARCH} in 
  armv6l)    ALPINE_ARCH=arm32v6;;
  armv7l)    ALPINE_ARCH=arm32v7;;
  x86_64|*)  ALPINE_ARCH=amd64;;  
esac 

export ALPINE_ARCH

echo "CPU: ${CPU_ARCH}"
echo "Alpine arch: ${ALPINE_ARCH}"
# echo "Image: ${IMAGE_NAME}"

docker-compose build && docker-compose push
# docker build -t ${IMAGE_NAME} --build-arg ALPINE_ARCH=${ALPINE_ARCH} .
# BUILD_RETURN=$?

# -- if build goes well and we have a registry, push it
# ([[ "${BUILD_RETURN}" -eq 0 ]] \
#   && docker-compose push) || exit ${BUILD_RETURN}
#  && docker tag ${IMAGE_NAME} ${DOCKER_REGISTRY}/${IMAGE_NAME} \
#  && docker push ${DOCKER_REGISTRY}/${IMAGE_NAME}) || exit ${BUILD_RETURN}
