#!/bin/bash 

#env $(cat .env | xargs) python beatplayer/mpplayer.py -a 0.0.0.0 -p 9000 -e mpv $@
#
#

env $(cat .env | xargs) python test.py -a 0.0.0.0 -p 9000 -e mpv $@
