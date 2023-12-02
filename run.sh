#!/bin/bash 

docker-compose -f docker-compose.yml -f services/beatplayer/docker-compose.yml -f services/switchboard/docker-compose.yml $@
