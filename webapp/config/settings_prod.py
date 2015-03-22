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
BEATPLAYER_SERVER = 'http://alarmpi:9000'
PLAYLIST_WORKING_FOLDER = "/media/sf_beater_working"
PLAYLIST_FILENAME = "playlist.txt"
