from .settings import *

ALLOWED_HOSTS = ['<ALLOWED_HOSTS>']

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATIC_URL = '<STATIC_URL>'

MEDIA_ROOT = '<MEDIA_ROOT>'
MEDIA_URL = '<MEDIA_URL>'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': 'localhost',
        'NAME': 'beater',
        'USER': '<BEATER USERNAME>',
        'PASSWORD': '<BEATER PASSWORD>',
        'OPTIONS': {
        	'sql_mode': 'STRICT_TRANS_TABLES'
        }
    }
}

#MUSIC_MOUNT = "/vagrant/mounts/music"
SWITCHBOARD_SERVER_HOST = "<WEBSOCKET HOST>"
SWITCHBOARD_SERVER_PORT = <WEBSOCKET PORT>
BEATPLAYER_SERVER = '<BEATPLAYER SERVER>'
BEATER_HOSTNAME = "<BEATER_HOSTNAME>"
BEATER_PORT = '80'
