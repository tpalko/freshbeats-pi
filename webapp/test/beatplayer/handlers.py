{
    'request': <WSGIRequest: POST '/health_response/'>, 
    'health_data': {
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
    }, 
    'health': {
        'success': True, 
        'message': '', 
        'data': {
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
    }, 
    'player': <beater.beatplayer.player.PlayerWrapper object at 0x7fec181f56a0>, 
    'e': TypeError("Can't convert 'float' object to str implicitly",)
}
