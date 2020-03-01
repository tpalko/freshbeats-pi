#!/bin/bash 

env $(cat .env | xargs) python3 mpplayer.py -a 0.0.0.0 -p 9000 -e mpv $@
