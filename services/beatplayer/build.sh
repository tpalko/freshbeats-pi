#!/bin/bash 

docker build -t beatplayer . \
 && docker tag beatplayer:latest frankendeb:5000/beatplayer:latest \
 && docker push frankendeb:5000/beatplayer:latest
