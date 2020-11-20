#!/bin/bash 

echo "$(cat test.env | xargs) python test/beatplayer/./player.py"
env $(cat test.env | xargs) python test/beatplayer/./player.py
