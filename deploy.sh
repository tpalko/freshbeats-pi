#!/bin/bash 

pushd $(dirname $0)
scp services/beatplayer/mpplayer.py pi@frankenpi: && \
  ssh pi@frankenpi "sudo rm -fv /opt/freshbeats/beatplayer/mpplayer.py && sudo mv -unv ~/mpplayer.py /opt/freshbeats/beatplayer && sudo systemctl daemon-reload && sudo systemctl restart beatplayer"
popd
