#!/bin/bash 

echo "$(cat dev.env | xargs) python manage.py $@.."
env $(cat dev.env | xargs) python manage.py $@
