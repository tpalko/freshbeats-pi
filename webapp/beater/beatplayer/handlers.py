import json
import logging
import sys
import traceback

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from beater.models import Device
from beater.switchboard.switchboard import SwitchboardClient
from beater.beatplayer.player import PlayerWrapper 

logger = logging.getLogger()
action_logger = logging.getLogger('beater.beatplayer.action')
health_logger = logging.getLogger('beater.beatplayer.health')

def playlist_select(request):
    if request.method == "POST":
        playlist_id = request.POST.get('playlist_id')
        if playlist_id:
            logger.debug("Setting playlist ID: %s" % playlist_id)
            request.session['playlist_id'] = playlist_id 
        else:
            logger.debug("Setting playlist ID: playlist_id not found on the request")
    return JsonResponse({'success': True})

def device_select(request):
    device_id = None 
    if request.method == "POST":
        device_id = request.POST.get('device_id')
        if device_id:
            logger.debug("Setting device ID: %s" % device_id)
            request.session['device_id'] = device_id             
        else:
            logger.debug("Setting device ID: device_id not found on the request")
    return JsonResponse({'success': True, "data": {"device_id": device_id}})
    
def mobile_select(request):
    mobile_id = None 
    if request.method == "POST":
        mobile_id = request.POST.get('mobile_id')
        if mobile_id:
            logger.debug("Setting mobile ID: %s" % mobile_id)
            request.session['mobile_id'] = mobile_id             
        else:
            logger.debug("Setting mobile ID: mobile_id not found on the request")
    return JsonResponse({'success': True, "data": {"mobile_id": mobile_id}})

def player(request, command):
    response = {'result': {}, 'success': False, 'message': ""}
    
    try:
        # -- type 'album' may be orphaned.. only referenced once in templates, included in one view, whose url is commented
        # if type == "album":
        #     return _album_command(request)
        albumid = request.POST.get('albumid', None)
        songid = request.POST.get('songid', None)
        artistid = request.POST.get('artistid', None)
        playlistsongid = request.POST.get('playlistsongid', None)
        
        device = Device.objects.get(pk=request.session['device_id'])
        playlist_id = request.session['playlist_id'] if 'playlist_id' in request.session else None 
        
        player = PlayerWrapper.getInstance(device_id=device.id)
        
        player_args = {
            'playlist_id': playlist_id, 
            'albumid': albumid, 
            'songid': songid, 
            'artistid': artistid, 
            'playlistsongid': playlistsongid,
            'logger': action_logger
        }

        logger.debug(f'Calling {command} with {player_args}')

        player.call(command, **player_args)
            
        response['success'] = True

    except:
        response['message'] = "%s: %s" % (str(sys.exc_info()[0].__name__), str(sys.exc_info()[1]))
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        SwitchboardClient.getInstance().publish_event('alert', json.dumps(response))

    return JsonResponse({'success': True})

@csrf_exempt
def player_complete(request):
    '''
    Ultra weirdness here..
    If 'force_play' is false..
    When beatplayer would return from a song prematurely and call this callback, it would fetch the next song and issue the play call, but it would be rejected..
    Because even though beatplayer returned prematurely, the process was still alive.
    So 'next' worked..
    The natural return at the end of a song also worked, because at that point the process was dead, so it didn't need to be forced.
    '''

    complete_response = json.loads(request.body.decode())
    logger.debug(complete_response)

    response = {'result': {}, 'success': False, 'message': ""}

    try:
        health_data = complete_response['data']
        
        if 'start' in health_data and health_data['start']:
            SwitchboardClient.getInstance().publish_event('append_player_output', json.dumps({ 'message': '', 'data': {'clear': True}}))
            
        if health_data['complete']:
            agent_base_url = health_data['agent_base_url']
            logger.debug("Complete event received from %s" % agent_base_url)
            device = Device.objects.filter(agent_base_url=agent_base_url).first()
            playlist_id = request.session['playlist_id'] if 'playlist_id' in request.session else None 
            player = PlayerWrapper.getInstance(device_id=device.id)
            player_args = {
                'playlist_id': playlist_id, 
                'success': complete_response['success'], 
                'message': complete_response['message'], 
                'data': health_data,
                'logger': action_logger
            }
            player.call("complete", **player_args)
        
        if complete_response['message']:
            logger.debug("player output: %s" % complete_response['message'])
            # -- \n are lost in the publish, so if we want newlines in the browser, the <br /> needs to replace here 
            publish_output = { 'message': complete_response['message'].replace("\n\n", "\n").replace("\n", "<br />"), 'data': {'clear': True} }
            SwitchboardClient.getInstance().publish_event('append_player_output', json.dumps(publish_output))
            
        response['success'] = True

    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        SwitchboardClient.getInstance().publish_event('alert', json.dumps(response))

    return JsonResponse(response)
    
# def _album_command(request):
# 
#     album = Album.objects.get(pk=request.POST.get('albumid'))
#     command = request.POST.get('command')
# 
#     if command == "keep":
# 
#         album.action = Album.DONOTHING
#         album.save()
#         response['albumid'] = album.id

# def _handle_command(command, **kwargs): #albumid=None, songid=None, artistid=None, success=True, message='', force_play=True):
#     '''
#     how do we want playback to behave?
#         keep a playlist with a cursor (current)
#         keep a player model that holds one song at a time
#         user controls how and when the cursor moves and when songs are loaded
#     * remove 'playlist' button - player is 'on', except when immediate commands are given
#     'playlist'
#         - is sticky on or off, even when stopped
#         - once on, only goes to off when:
#             - a single song is played
#             - effectively, playing a single song is the same as splice + next, but without actually adding the song to the playlist
#         - once off, goes to on when:
#             - song completes
#             - 'next'
#     'complete'
#         - if playing, turns on playlist and picks up at cursor
#         - if stopped, does nothing (only happens when already stopped and a single song is played)
#         - should never be paused
#     'enqueue' tacks song or album onto the end, no effect on playback
#     'splice' sticks song or album in the middle, no effect on playback
#     'play song'
#         - if playing or paused:
#             - if on playlist, advances cursor to next song (preference?), turns off playlist, issues call for this song (don't add to playlist)
#             - if off playlist, issues call for this song (don't add to playlist)
#         - if stopped, issues call for this song (don't add to playlist)
#             - call includes callback tag for 'that was a single play, don't continue playing anything else'
#             - or add a fourth state 'waiting to be stopped when complete'
#     'play album'
#         - splice album in, advance cursor
#         - for simplicity, this is actually 'splice album', there's no such thing as 'play album aside from playlist'
#     'stop'
#         - stops playback, leave cursor (preference?) and playlist on or off
#         - keep current song in player
#     'play'
#         - if stopped and song in player, issues call for song
#         - if stopped and no song in player
#             - turns on playlist, issues call for song at cursor
#         - if playing, does nothing
#         - if paused, unpause
#     'pause'
#         - if playing, pause
#         - if paused, play
#         - if stopped, nothing
#     'next'
#         - if off playlist, turns on playlist
#         - else advances cursor
#         - loads song at cursor
#         - if playing, issues play
#     future:
#         - implement shuffle
#         - implement 'side play' for playing albums without affecting playlist
#         - preferences:
#             - auto play on next
#             - auto advance
#     '''
#     return JsonResponse({'success': True})

'''
def _init_playlist():
    playlist_file = os.path.join(settings.PLAYLIST_WORKING_FOLDER, settings.PLAYLIST_FILENAME)
    logger.debug("opening %s" %playlist_file)
    return open(playlist_file, "wb")
'''

'''
def _write_song_to_playlist(song, playlist):
    full_path = _get_song_filepath(song)
    playlist.write(full_path.encode('utf8'))
'''
