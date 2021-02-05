import json
import logging
import os
import sys
import traceback
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse, JsonResponse, QueryDict
from django.shortcuts import render, render_to_response, redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods #require_GET, require_POST, 
from django.views.decorators.csrf import csrf_exempt

from ..models import Album, Artist, AlbumCheckout, Song, AlbumStatus, PlaylistSong, Device
from ..common.util import capture
from ..common.switchboard import _publish_event
from .player import PlayerWrapper 
from .health import BeatplayerRegistrar

logger = logging.getLogger(__name__)

def register_client(request):    
    user_agent = request.POST.get('userAgent')
    connection_id = request.POST.get('connectionId')
    request.session['switchboard_connection_id'] = connection_id
    request.session['user_agent'] = user_agent 
    session_key = request.session.session_key
    return JsonResponse({'success': True})

@csrf_exempt
@require_http_methods(['POST'])
def device_health_loop(request):
    response = {'success': False, 'message': ''}
    try:
        body = json.loads(request.body.decode())
        agent_base_url = body['agent_base_url'] # request.POST.get('agent_base_url')
        if agent_base_url:
            beatplayer = BeatplayerRegistrar.getInstance(agent_base_url)
            beatplayer.check_if_health_loop()
            response['success'] = True
        else:
            response['message'] = "agent_base_url is %s" % agent_base_url
    except:
        response['message'] = str(sys.exc_info()[1])
    return JsonResponse(response)

@csrf_exempt
def health_response(request):
    
    response = {'message': "", 'success': False, 'result': {}}
    try:
        health = json.loads(request.body.decode())
        
        if not health['success'] and health['message'] and len(health['message']) > 0:
            _publish_event('message', json.dumps(health['message']))
        
        logger.debug("health response: %s" % json.dumps(health, indent=4))
        health_data = health['data']
        
        #logger.debug('Health response: %s' % (json.dumps(health_data, indent=4)))
        agent_base_url = health_data['agent_base_url']
        
        logger.debug("Parsing health response in BeatplayerRegistrar..")
        beatplayer = BeatplayerRegistrar.getInstance(agent_base_url=agent_base_url)
        beatplayer.log_health_response(health_data)
        
        with beatplayer.device(read_only=True) as device:
            logger.debug("Parsing health response in PlayerWrapper..")
            playlist_id = request.session['playlist_id'] if 'playlist_id' in request.session else None 
            player = PlayerWrapper.getInstance(device_id=device.id)
            player.call('parse_state', playlist_id=playlist_id, health_data=health_data)
        
        response['success'] = True 
    except Exception as e:
        response['message'] = str(sys.exc_info()[1])
        logger.error(sys.exc_info()[0])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        # logger.error(dir(sys.exc_info()[2]))
        # logger.error(sys.exc_info()[2].tb_frame.f_code)
        # logger.error(sys.exc_info()[2].tb_frame.f_lineno)
        # logger.error(sys.exc_info()[2].tb_frame.f_locals)
        _publish_event('alert', json.dumps({'message': response['message']}))
    
    logger.debug("Finished processing health response")
    return JsonResponse(response)

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
    if request.method == "POST":
        device_id = request.POST.get('device_id')
        if device_id:
            logger.debug("Setting device ID: %s" % device_id)
            request.session['device_id'] = device_id 
        else:
            logger.debug("Setting device ID: device_id not found on the request")
    return JsonResponse({'success': True})

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
        player.call(command, playlist_id=playlist_id, albumid=albumid, songid=songid, artistid=artistid, playlistsongid=playlistsongid)
            
        response['success'] = True

    except:
        response['message'] = "%s: %s" % (str(sys.exc_info()[0].__name__), str(sys.exc_info()[1]))
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('alert', json.dumps(response))

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
            _publish_event('append_player_output', json.dumps({ 'message': '', 'data': {'clear': True}}))
            
        if health_data['complete']:
            agent_base_url = health_data['agent_base_url']
            logger.debug("Complete event received from %s" % agent_base_url)
            device = Device.objects.filter(agent_base_url=agent_base_url).first()
            playlist_id = request.session['playlist_id'] if 'playlist_id' in request.session else None 
            player = PlayerWrapper.getInstance(device_id=device.id)
            player.call("complete", playlist_id=playlist_id, success=complete_response['success'], message=complete_response['message'], data=health_data)
        
        if complete_response['message']:
            logger.debug("player output: %s" % complete_response['message'])
            # -- \n are lost in the publish, so if we want newlines in the browser, the <br /> needs to replace here 
            publish_output = { 'message': complete_response['message'].replace("\n\n", "\n").replace("\n", "<br />"), 'data': {'clear': True} }
            _publish_event('append_player_output', json.dumps(publish_output))
            
        response['success'] = True

    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('alert', json.dumps(response))

    return JsonResponse(response)

def beatplayer_status(request):    
    response = {'result': {}, 'success': False, 'message': ""}
    try:
        logger.info("/beatplayer_status called, triggering status display")
        agent_base_url = None
        if 'device_id' in request.session:
            device = Device.objects.get(pk=request.session['device_id'])
            agent_base_url = device.agent_base_url
            beatplayer = BeatplayerRegistrar.getInstance(agent_base_url=agent_base_url)        
            beatplayer.check_if_health_loop()
            response['success'] = True
    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('message', json.dumps(response['message']))

    return JsonResponse(response)

def player_status_and_state(request):

    response = {'result': {}, 'success': False, 'message': ""}

    try:
        if 'device_id' not in request.session:
            raise Exception('device_id not found in session when attempting to trigger player show_player_status')
            
        device = Device.objects.get(pk=request.session['device_id'])            
        #playlist_id = request.session['playlist_id'] if 'playlist_id' in request.session else None 
        player = PlayerWrapper.getInstance(device_id=device.id)
        player.show_player_status()
        response['success'] = True
    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('message', json.dumps(response['message']))

    return JsonResponse({'success': True})
    
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
