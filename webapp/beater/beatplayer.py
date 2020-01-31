from django.shortcuts import render
from django.shortcuts import render_to_response
from django.shortcuts import redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.http import HttpResponse, JsonResponse, QueryDict
from django.conf import settings
from django.db.models import Q
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
import os
import sys
from .models import Album, Artist, AlbumCheckout, Song, AlbumStatus, PlaylistSong
import xmlrpclib
import logging
import traceback
import json
import random
import socket
import requests
import threading
import re
import time
from cStringIO import StringIO
from util import capture
from switchboard import _publish_event

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Setting path for RPi: %s" % settings.BEATPLAYER_SERVER)
beatplayer_proxy = xmlrpclib.ServerProxy(settings.BEATPLAYER_SERVER)
health_response = beatplayer_proxy.healthz()
logger.info(json.dumps(health_response))

PLAYER_STATE_STOPPED = 'stopped'
PLAYER_STATE_PLAYING = 'playing'
PLAYER_STATE_PAUSED = 'paused'

mute = False
shuffle = False
playlist = True

'''
             | shuffle off                 | shuffle on         |
-------------------------------------------------------------
playlist off | no play                    | any song             |
playlist on  | playlist after current     | playlist unplayed |

'''

player_state = PLAYER_STATE_STOPPED

# logger.debug("Setting callback for RPi")
# beatplayer_proxy.set_callback("http://%s:%s/player_complete" % (settings.BEATER_HOSTNAME, settings.BEATER_PORT))

def player(request, command, albumid=None, songid=None):

    #problem = None
    #player_info = None

    #command = request.POST.get('command', None) # surprise, playlist, next, shuffle, enqueue_album, play/enqueue_song, pause, stop, mute, keep
    #albumid = request.POST.get('albumid', None)
    #songid = request.POST.get('songid', None)

    #logger.debug("Got command: %s" % command)

    _handle_command(command, albumid, songid, force_play=True)


@csrf_exempt
def command(request, type):
    '''/command/album or /command/player'''
    response = {'result': {}, 'success': False, 'message': ""}

    try:
        # -- type 'album' may be orphaned.. only referenced once in templates, included in one view, whose url is commented
        if type == "album":
            return _album_command(request)
        elif type == "player":

            command = request.POST.get('command', None) # surprise, playlist, next, shuffle, enqueue_album, play/enqueue_song, pause, stop, mute, keep
            albumid = request.POST.get('albumid', None)
            songid = request.POST.get('songid', None)

            return _handle_command(command, albumid=albumid, songid=songid)

        response['success'] = True

    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('alert', json.dumps(response))

    return HttpResponse(json.dumps({'success': True}))


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

    logger.info("player_complete called")
    response = {'result': {}, 'success': False, 'message': ""}

    try:

        logger.debug("Player state: %s" % player_state)

        if player_state == PLAYER_STATE_PLAYING:
            logger.info("Currently playing.. getting next..")
            _handle_command("player_complete")

        response['success'] = True

    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('alert', json.dumps(response))

    return HttpResponse(json.dumps({'success': True}))


@csrf_exempt
def player_status_and_state(request):

    response = {'result': {}, 'success': False, 'message': ""}

    try:

        current_song = PlaylistSong.objects.order_by('id').filter(is_current=True).last()

        if current_song:
            _show_player_status(current_song.song)

        logger.debug("player status and state")
        _show_player_state()

        response['success'] = True

    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('alert', json.dumps(response))

    return HttpResponse(json.dumps({'success': True}))

def _album_command(request):

    album = Album.objects.get(pk=request.POST.get('albumid'))
    command = request.POST.get('command')

    if command == "keep":

        album.action = Album.DONOTHING
        album.save()
        response['albumid'] = album.id

def _handle_command(command, albumid=None, songid=None, force_play=True):

    global player_state
    global playlist
    global shuffle
    global mute

    logger.debug("Playlist: %s, Shuffle: %s" % (playlist, shuffle))

    next_song = None
    next_playlistsong = None
    send_kill = False

    if command == "player_complete":

        player_state = PLAYER_STATE_PLAYING

        if playlist:
            logger.info("Got 'next', running playlist..")
            next_playlistsong = _get_next_playlistsong()
        elif shuffle:
            logger.info("Got 'next', not running playlist, but shuffling..")
            next_song = _get_next_song()
        else:
            logger.info("Got 'next', but not running playlist - what do to?")

    elif command == "surprise":

        shuffle = True
        playlist = False
        next_song = _get_next_song()

    elif command == "playlist":

        if not playlist:
            playlist = True

        if player_state == PLAYER_STATE_PLAYING:
            logger.info("Already playing playlist..")
        elif player_state == PLAYER_STATE_PAUSED:
            player_state = PLAYER_STATE_PLAYING
            beatplayer_proxy.pause()
        elif player_state == PLAYER_STATE_STOPPED:
            player_state = PLAYER_STATE_PLAYING
            new_playlistsong = _get_current_song()

    elif command == "next":

        if player_state != PLAYER_STATE_STOPPED:
            beatplayer_proxy.stop()
        else:
            if playlist:
                next_playlistsong = _get_next_playlistsong()
            else:
                next_song = _get_next_song()


    elif command == "shuffle":

        shuffle = not shuffle

    elif command == "play":

        if songid is not None:
            logger.debug("Fetching song %s" % songid)
            next_song = Song.objects.get(pk=songid)
        elif albumid is not None:
            logger.debug("Fetching album %s" % albumid)
            album = Album.objects.get(pk=albumid)
            first_song = None
            for song in album.song_set.all().order_by('name'):
                playlistsong = PlaylistSong(song=song)
                playlistsong.save()
                if not first_song:
                    first_song = playlistsong
                    next_playlistsong = first_song
        elif player_state == PLAYER_STATE_PLAYING:
            # -- no op
            logger.info("already playing..")
        elif player_state == PLAYER_STATE_PAUSED:
            player_state = PLAYER_STATE_PLAYING
            beatplayer_proxy.pause()
        elif player_state == PLAYER_STATE_STOPPED:
            player_state = PLAYER_STATE_PLAYING
            new_playlistsong = _get_current_song()
        # elif shuffle:
        #     next_song = _get_next_song()

    elif command == "enqueue":

        if albumid is not None:

            album = Album.objects.get(pk=albumid)

            for song in album.song_set.all().order_by('name'):
                playlistsong = PlaylistSong(song=song)
                playlistsong.save()
                if next_playlistsong is None:
                    next_playlistsong = playlistsong

        elif songid is not None:

            song = Song.objects.get(pk=songid)

            playlistsong = PlaylistSong(song=song)
            playlistsong.save()
            if next_playlistsong is None:
                next_playlistsong = playlistsong

        # - 'soft' play to start playback if it isn't already
        force_play = False

    elif command == "pause":
        if player_state == PLAYER_STATE_PAUSED:
            player_state = PLAYER_STATE_PLAYING
        else:
            player_state = PLAYER_STATE_PAUSED
        beatplayer_proxy.pause()

    elif command == "stop":
        # if player_state == PLAYER_STATE_STOPPED:
        #     player_state = PLAYER_STATE_PLAYING
        # else:
        player_state = PLAYER_STATE_STOPPED

        beatplayer_proxy.stop()

    elif command == "mute":
        mute = not mute
        beatplayer_proxy.mute()

    if next_song or next_playlistsong:

        if next_song is None and next_playlistsong is not None:
            next_song = next_playlistsong.song

        logger.debug("Playing song %s" % next_song.name)
        played = _play(next_song, force_play)

        if played:
            _show_player_status(next_song)
            if next_playlistsong is not None:
                _set_current_song(next_playlistsong)

    logger.debug("handled command %s" % command)
    _show_player_state()

    return HttpResponse(json.dumps({'success': True}))

def _play(song, force_play=False):

    global player_state

    played = beatplayer_proxy.play(_get_song_filepath(song), "http://%s:%s/player_complete/" % (settings.FRESHBEATS_EXTERNAL_HOST, settings.FRESHBEATS_EXTERNAL_PORT), force_play)
    player_state = PLAYER_STATE_PLAYING
    return played

def _show_player_status(song):

    logger.debug("Showing status..")

    status_info = {
        "Title": song.name,
        "Artist": song.album.artist,
        "Album": song.album.name,
        "Year": "?",
        "Track": "?",
        "Genre": "?"
    }

    _publish_event('player_status', json.dumps(render_to_string('_player_status.html', {'status': status_info})))


def _show_player_state():
    '''Publish state of player through websocket'''
    global shuffle
    global mute
    _publish_event('player_state', json.dumps({
        'shuffle': "on" if shuffle else "off",
        'mute': "on" if mute else "off"
    }))


def _get_current_song():
    current_playlistsong = PlaylistSong.objects.filter(is_current=True).first()
    return current_playlistsong

def _get_next_song():
    '''Returns a randomly chosen song'''
    logger.debug("Fetching next song..")
    next_song = random.choice(Song.objects.all())
    logger.debug("Fetched %s" % next_song.name)
    return next_song


def _get_next_playlistsong():

    logger.debug("Fetching next playlist song..")
    global shuffle
    next_playlistsong = None

    if shuffle:
        songs_left = PlaylistSong.objects.filter(played=False)
        if len(songs_left) > 0:
            next_playlistsong = random.choice(songs_left)

    else:
        current_song = PlaylistSong.objects.filter(is_current=True).first()

        if current_song is not None:
            next_playlistsong = PlaylistSong.objects.filter(id__gt=current_song.id).order_by('id').first()

        if next_playlistsong is None:
            next_playlistsong = PlaylistSong.objects.all().order_by('id').first()

    if next_playlistsong is not None:
        logger.debug("Fetched %s" % next_playlistsong.song.name)

    return next_playlistsong


def _set_current_song(playlistsong):

    current_playlistsong = PlaylistSong.objects.filter(is_current=True).first()

    if current_playlistsong is not None:
        current_playlistsong.is_current = False
        current_playlistsong.played = True
        current_playlistsong.save()

    playlistsong.is_current = True
    playlistsong.save()


def _get_song_filepath(song):

    beatplayer_music_folder = None

    if not beatplayer_music_folder:
        try:
            logger.debug("Calling to get music folder..")
            beatplayer_music_folder = beatplayer_proxy.get_music_folder()
            logger.debug("Music folder found: %s" % beatplayer_music_folder)
        except:
            logger.error("Music folder NOT found")

    if beatplayer_music_folder is None:
        raise Exception("beatplayer is not responding")

    return "%s/%s/%s/%s" % (beatplayer_music_folder, song.album.artist, song.album.name, song.name)


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
