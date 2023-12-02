import os
import django
import sys 
print(sys.path)
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'

django.setup()
from beater.beatplayer.player import PlayerWrapper 
from beater.models import Device 

health_data = {
    'current_command': ['mpv', 
        '--quiet=yes', 
        '--no-video', 
        '--volume=90', 
        '--input-ipc-server=/tmp/mpv.sock', 
        '/media/storage/music/Jawbox/Grippe/Jawbox_Grippe_14_Secret History.mp3'], 
    'music_folder_mounted': True, 
    'time': [35.230483, 
        99.681839], 
    'ps': {
        'returncode': None, 
        'is_alive': True, 
        'pid': 30639
    }, 
    'socket': {
        'healthy': True
    }
}

def test(player):
    player.parse_state(health_data)

if __name__ == "__main__":
    player = PlayerWrapper.getInstance()
    test(player)
