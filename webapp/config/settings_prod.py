from settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
		'HOST': 'frankenbeater',
        'NAME': 'beater',
        'USER': 'dev',
        'PASSWORD': 'dev'
    }
}

#MUSIC_MOUNT = "/media/sf_music"
SWITCHBOARD_SERVER_HOST = "127.0.0.1"
SWITCHBOARD_SERVER_PORT = 3000
BEATPLAYER_SERVER = 'http://alarmpi:9000'
PLAYLIST_WORKING_FOLDER = "/media/sf_beater_working"
PLAYLIST_FILENAME = "playlist.txt"
BEATER_HOSTNAME = "frankenbeater"
BEATER_PORT = '8000'