#!/bin/bash 

CPUARCH=$(uname -m)

docker build -t beatplayer:${CPUARCH} . \
 && docker tag beatplayer:${CPUARCH} registry.palkosoftware.net:5000/beatplayer:${CPUARCH} \
 && docker push registry.palkosoftware.net:5000/beatplayer:${CPUARCH}
