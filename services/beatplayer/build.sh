#!/bin/bash 

CPUARCH=$(uname -m)

docker build -t beatplayer:${CPUARCH} . \
 && docker tag beatplayer:${CPUARCH} frankendeb:5000/beatplayer:${CPUARCH} \
 && docker push frankendeb:5000/beatplayer:${CPUARCH}
