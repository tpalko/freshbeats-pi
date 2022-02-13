#!/usr/bin/env python3

from ingest import *

TESTFILE = '/media/storage/music/The Lemonheads/Lovey/track01.cdda.wav.mp3'
print(f'TESTFILE = {TESTFILE}')

config = {
    'artist_filter': None,
    'tags_menu': True, 
    'sha1_scan': True, 
    'id3_scan': True, 
    'purge': False, 
    'skip_verification': False
}

ingest = Ingest(**config)

'''
import os
import sys 
import django 

sys.path.append(join(os.path.dirname(__file__), '../../webapp'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'
django.setup()

from beater.models import Artist, Album, Song, AlbumCheckout, AlbumStatus
from mutagen import easyid3, id3
'''
