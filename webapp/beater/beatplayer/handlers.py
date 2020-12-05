import json
import logging
import os
import re
import requests
import socket
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta
from xmlrpc import client

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse, JsonResponse, QueryDict
from django.shortcuts import render, render_to_response, redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from ..models import Album, Artist, AlbumCheckout, Song, AlbumStatus, PlaylistSong, Player
from ..common.util import capture
from ..common.switchboard import _publish_event
from .player import PlayerWrapper 
from .health import BeatplayerRegistrar

logger = logging.getLogger(__name__)

def register_client(request):
    logger.debug(request.POST)
    user_agent = request.POST.get('userAgent')
    connection_id = request.POST.get('connectionId')
    request.session['switchboard_connection_id'] = connection_id
    request.session['user_agent'] = user_agent 
    session_key = request.session.session_key
    logger.debug(dir(request.session))
    # -- add these values to the user session 
    return JsonResponse({'success': True})

@csrf_exempt
def health_response(request):
    
    response = {'message': "", 'success': False, 'result': {}}
    try:
        health = json.loads(request.body.decode())
        
        if not health['success'] and health['message'] and len(health['message']) > 0:
            _publish_event('message', json.dumps(health['message']))
            
        health_data = health['data']
        
        logger.debug('Health response: %s' % (json.dumps(health_data, indent=4)))
        
        logger.debug("Parsing health response in PlayerWrapper..")
        player = PlayerWrapper.getInstance()
        player.parse_state(health_data)
            
        logger.debug("Parsing health response in BeatplayerRegistrar..")
        beatplayer = BeatplayerRegistrar.getInstance()
        beatplayer.log_health_response(health_data)
        
        response['success'] = True 
    except Exception as e:
        response['message'] = sys.exc_info()[1]
        logger.error(dir(sys.exc_info()[2]))
        logger.error(sys.exc_info()[2].tb_frame.f_code)
        logger.error(sys.exc_info()[2].tb_frame.f_lineno)
        logger.error(sys.exc_info()[2].tb_frame.f_locals)
        _publish_event('alert', json.dumps({'message': str(sys.exc_info()[1])}))
    
    return JsonResponse(response)

def player_select(request):
    if request.method == "POST":
        player_id = request.POST.get('player_id')
        if player_id:
            request.session['player_id'] = player_id 
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

        player = PlayerWrapper.getInstance()
        player.call(command, albumid=albumid, songid=songid, artistid=artistid, playlistsongid=playlistsongid)
            
        response['success'] = True

    except:
        response['message'] = str(sys.exc_info()[1])
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
        player = PlayerWrapper.getInstance()
        if complete_response['data']['complete']:
            player.call("complete", success=complete_response['success'], message=complete_response['message'], data=complete_response['data'])
            _publish_event('clear_player_output')
        else:
            logger.debug("player output: %s" % complete_response['message'])
            _publish_event('append_player_output', json.dumps(complete_response['message']))
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
        beatplayer = BeatplayerRegistrar.getInstance()        
        beatplayer.show_status()
        response['success'] = True
    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('message', json.dumps(response['message']))

    return JsonResponse({'success': True})

def player_status_and_state(request):

    response = {'result': {}, 'success': False, 'message': ""}

    try:
        player = PlayerWrapper.getInstance()
        player.call("show_player_status")
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
