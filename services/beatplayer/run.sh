#!/bin/bash 

ARCH=$(uname -m) docker-compose up --build --force-recreate -d
