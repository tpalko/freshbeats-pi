from settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': 'localhost',
        'NAME': 'beater',
        'USER': 'dev',
        'PASSWORD': 'dev'
    }
}

#MUSIC_MOUNT = "/vagrant/mounts/music"
SWITCHBOARD_SERVER_HOST = "127.0.0.1"
SWITCHBOARD_SERVER_PORT = 3000
BEATPLAYER_SERVER = 'http://alarmpi:9000' #192.168.33.11:9000'
PLAYLIST_WORKING_FOLDER = "/vagrant/mounts/beater_working"
PLAYLIST_FILENAME = "playlist.txt"
BEATER_HOSTNAME = "mac-mallingapple.ad.sei.cmu.edu"
BEATER_PORT = '8000'