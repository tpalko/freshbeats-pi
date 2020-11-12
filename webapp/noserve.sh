#!/bin/bash 

export FRESHBEATS_SERVING=0 
env $(cat dev.env | xargs) python manage.py $@
