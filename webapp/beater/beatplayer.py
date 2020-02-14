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
from .models import Album, Artist, AlbumCheckout, Song, AlbumStatus, PlaylistSong, Player
from xmlrpc import client
import logging
import traceback
import json
import random
import socket
import requests
import threading
import re
import time
from .util import capture
from .switchboard import _publish_event

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Setting path for RPi: %s" % settings.BEATPLAYER_SERVER)
beatplayer_proxy = client.ServerProxy(settings.BEATPLAYER_SERVER)
health_attempts = 0
health_response = None
while not health_response:
    try:
        health_response = beatplayer_proxy.healthz()
    except:
        logger.warn("beatplayer not alive..")
        logger.warn(sys.exc_info()[1])
    health_attempts = health_attempts + 1
    if health_response:
        health_response['attempts'] = health_attempts
logger.info(json.dumps(health_response, indent=2))

class PlaylistBacking():
    pass 

class DatabaseBacking(PlaylistBacking):
    
    def get_current(self):
        return PlaylistSong.objects.filter(is_current=True).first()
    def get_last(self):
        return PlaylistSong.objects.all().order_by('queue_number').reverse().first()
    def get_random(self):
        return random.choice(PlaylistSong.objects.all()) 
    def get_next(self):
        return PlaylistSong.objects.filter(queue_number__gt=self.current_playlistsong.queue_number).order_by('queue_number').first()
    def get_first(self):
        return PlaylistSong.objects.all().order_by('queue_number').first()
    def get_remaining(self):
        return PlaylistSong.objects.filter(queue_number__gt=self.current_playlistsong.queue_number)

class EmptyBacking(PlaylistBacking):
    pass

class Playlist():
    '''
    Playlist maintains a queue and a cursor.
    '''

    current_playlistsong = None
    max_queue_number = 0

    def __init__(self, *args, **kwargs):
        self.current_playlistsong = PlaylistSong.objects.filter(is_current=True).first()
        self.max_queue_number = PlaylistSong.objects.all().order_by('queue_number').reverse().first().queue_number        

    def __str__(self):
        playlistsongs = PlaylistSong.objects.all().order_by('queue_number');
        return render_to_string("_playlist.html", {'playlistsongs': playlistsongs})
        
    def advance_cursor(self, shuffle=False):

        if self.current_playlistsong is not None:
            self.current_playlistsong.is_current = False
            self.current_playlistsong.save()
        
        if shuffle:
            valid_playlistsongs = PlaylistSong.objects.filter(queue_number__ne=self.current_playlistsong.queue_number)
            self.current_playlistsong = random.choice(valid_playlistsongs)
        elif self.current_playlistsong.queue_number < self.max_queue_number:
            self.current_playlistsong = self._get_remaining_playlistsongs().order_by('queue_number').first()
        else:
            self.current_playlistsong = PlaylistSong.objects.order_by('queue_number').first()
        
        self.current_playlistsong.is_current = True
        self.current_playlistsong.save()
        
    def get_current_playlistsong(self):
        return self.current_playlistsong
    
    def _get_remaining_playlistsongs(self):
        return PlaylistSong.objects.filter(queue_number__gt=self.current_playlistsong.queue_number)
        
    def increment_current_playlistsong_play_count(self):
        if self.current_playlistsong:
            self.current_playlistsong.play_count = self.current_playlistsong.play_count + 1
            self.current_playlistsong.save()

    def add_song_to_playlist(self, song, queue_number=None):
        if not queue_number:
            self.max_queue_number = self.max_queue_number + 1
            queue_number = self.max_queue_number
        new_playlistsong = PlaylistSong(song=song, queue_number=queue_number)
        new_playlistsong.save()

    def add_album_to_playlist(self, album):
        for i, song in enumerate(album.song_set.all(), 1):
            self.add_song_to_playlist(song)
    
    def add_artist_to_playlist(self, artist):
        for i, album in enumerate(artist.album_set.all(), 1):
            for j, song, in enumerate(album.song_set.all(), 1):
                self.add_song_to_playlist(song)
    
    def _bump_remaining_playlistsongs(self, bump_count=1):
        # -- bump the queue number of all future songs
        next_playlistsongs = self._get_remaining_playlistsongs()
        for playlistsong in next_playlistsongs:
            playlistsong.queue_number = playlistsong.queue_number + bump_count
            playlistsong.save()        
        self.max_queue_number = self.max_queue_number + bump_count
        
    def splice_song(self, song):
        self._bump_remaining_playlistsongs(1)
        self.add_song_to_playlist(song, self.current_playlistsong.queue_number + 1)

    def splice_album(self, album):        
        song_count = album.song_set.count()
        self._bump_remaining_playlistsongs(song_count)
        # -- splice in the album as the next queue numbers 
        for i, song in enumerate(album.song_set.all(), 1):
            self.add_song_to_playlist(song, self.current_playlistsong.queue_number + i)

    def splice_artist(self, artist):
        song_count = sum([ album.song_set.count() for album in artist.album_set.all() ])
        self._bump_remaining_playlistsongs(song_count)
        bump = 0
        for i, album in enumerate(artist.album_set.all(), 1):
            for j, song, in enumerate(album.song_set.all(), 1):
                bump = bump + 1
                self.add_song_to_playlist(song, self.current_playlistsong.queue_number + bump)
                
class PlayerObj():
    '''
    Player implements standard playback actions with a Playlist and additional logic and state.
    '''
    
    mute_state = False
    shuffle_state = False
    playlist_mode = Player.PLAYLIST_MODE_ON
    playlist = None
    state = Player.PLAYER_STATE_STOPPED
    song = None
    cursor_mode = Player.CURSOR_MODE_NEXT

    def __init__(self, *args, **kwargs):
        # self._load()
        self.playlist = Playlist()
        self.song = self.playlist.get_current_playlistsong().song

    def get_status(self):
        pass

    def _beatplayer_play(self, song):
        force_play = True
        response = beatplayer_proxy.play(_get_song_filepath(song), "http://%s:%s/player_complete/" % (settings.FRESHBEATS_EXTERNAL_HOST, settings.FRESHBEATS_EXTERNAL_PORT), force_play)
        if response:
            self.playlist.increment_current_playlistsong_play_count()
        
    def _beatplayer_stop(self):
        beatplayer_proxy.stop()
    
    def _beatplayer_mute(self):
        beatplayer_proxy.mute()
        
    def _beatplayer_pause(self):
        beatplayer_proxy.pause()
    
    def _load(self):
        players = Player.objects.all()
        if len(players) > 0:
            player = players[0]
            self.mute_state = player.mute_state
            self.shuffle_state = player.shuffle_state
            self.playlist_mode = player.playlist_mode
            self.state = player.state
            self.cursor_mode = player.cursor_mode
            
    def _save(self):
        player = Player()
        players = Player.objects.all()
        if len(players) > 0:
            player = players[0]        
        player.mute_state = self.mute_state
        player.shuffle_state = self.shuffle_state
        player.playlist_mode = self.playlist_mode
        player.state = self.state
        player.cursor_mode = self.cursor_mode
        player.save()
    
    def call(self, command, **kwargs):
        
        logger.debug("player call, command: %s" % command)
        logger.debug(kwargs)
            
        f = self.__getattribute__(command)
        f(**kwargs)

        self._save()
        _show_player_status()
        _publish_event('playlist_update', json.dumps(str(self.playlist)))
    
    def complete(self, success=True, message=''):        
        if success and self.state != Player.PLAYER_STATE_STOPPED:
            if self.cursor_mode == Player.CURSOR_MODE_NEXT:
                self.playlist.advance_cursor(shuffle=self.shuffle_state)
                self.song = self.playlist.get_current_playlistsong().song
            self._beatplayer_play(self.song)
            self.playlist_mode = Player.PLAYLIST_MODE_ON
            self.state = Player.PLAYER_STATE_PLAYING
        if not success:
            self.state = Player.PLAYER_STATE_STOPPED
            _publish_event('message', json.dumps({'message': message}))
    
    def toggle_shuffle(self):
        self.shuffle_state = not self.shuffle_state
    
    def mute(self):
        self._beatplayer_mute()
        self.mute_state = not self.mute_state

    def pause(self):
        if self.state == Player.PLAYER_STATE_PAUSED:
            self._beatplayer_pause()
            self.state = Player.PLAYER_STATE_PLAYING
        elif self.state == Player.PLAYER_STATE_PLAYING:
            self._beatplayer_pause()
            self.state = Player.PLAYER_STATE_PAUSED
    
    def stop(self):
        if self.state != Player.PLAYER_STATE_STOPPED:
            self.state = Player.PLAYER_STATE_STOPPED
            self._beatplayer_stop()
            
    def play(self, **kwargs):
        song = None 
        album = None 
        artist = None 
        if 'songid' in kwargs and kwargs['songid'] is not None:  
            songid = kwargs['songid']
            song = Song.objects.get(pk=songid)
            self._play_song(song)
        elif 'albumid' in kwargs and kwargs['albumid'] is not None:
            albumid = kwargs['albumid']
            album = Album.objects.get(pk=albumid)
            self._play_album(album)
        elif 'artistid' in kwargs and kwargs['artistid'] is not None:
            artistid = kwargs['artistid']
            artist = Artist.objects.get(pk=artistid)
            self._play_artist(artist)
        else:
            if self.state == Player.PLAYER_STATE_STOPPED and self.song:
                self._beatplayer_play(self.song)
            elif self.state == Player.PLAYER_STATE_PAUSED:
                self._beatplayer_pause()
            self.state = Player.PLAYER_STATE_PLAYING
    
    def splice(self, song=None, album=None, artist=None):
        if song:
            self.splice_song(song)
        elif album:
            self.splice_album(album)
        elif artist:
            self.splice_artist(artist)
    
    def enqueue(self, song=None, album=None, artist=None):
        if song:
            self.add_song(song)
        elif album:
            self.add_album(album)
        elif artist:
            self.add_artist(artist)

    # -- play_song and play_album are both 'off playlist' operations
    # -- but there's currently no such thing as 'off playlist'
    # -- play_song can do it, because it's only one song, and we can trigger state change on complete or next 
    # -- play_album can't do that, so we splice it
    def _play_song(self, song):
        # -- instead of splice, this should work with a 'side playlist'
        self.shuffle_state = False 
        self.splice_song(song)
        if self.state != Player.PLAYER_STATE_STOPPED:
            self._beatplayer_stop()
        else:
            self.playlist.advance_cursor(shuffle=self.shuffle_state)
            self.song = self.playlist.get_current_playlistsong().song 
            self._beatplayer_play(self.song)
            self.state = Player.PLAYER_STATE_PLAYING
        
    def _play_album(self, album):
        # -- instead of splice, this should work with a 'side playlist'
        self.shuffle_state = False 
        self.splice_album(album)
        if self.state != Player.PLAYER_STATE_STOPPED:
            self._beatplayer_stop()
        else:
            self.playlist.advance_cursor(shuffle=self.shuffle_state)
            self.song = self.playlist.get_current_playlistsong().song
            self._beatplayer_play(self.song)            
            self.state = Player.PLAYER_STATE_PLAYING

    def _play_artist(self, artist):
        # -- instead of splice, this should work with a 'side playlist'
        self.shuffle_state = False 
        self.splice_artist(artist)
        if self.state != Player.PLAYER_STATE_STOPPED:
            self._beatplayer_stop()
        else:
            self.playlist.advance_cursor(shuffle=self.shuffle_state)
            self.song = self.playlist.get_current_playlistsong().song
            self._beatplayer_play(self.song)            
            self.state = Player.PLAYER_STATE_PLAYING
            
    def add_song(self, song):
        self.playlist.add_song_to_playlist(song)
    
    def add_album(self, album):
        self.playlist.add_album_to_playlist(album)
    
    def add_artist(self, artist):
        self.playlist.add_artist_to_playlist(artist)
        
    def splice_song(self, song):
        self.playlist.splice_song(song)
    
    def splice_album(self, album):
        self.playlist.splice_album(album)
    
    def splice_artist(self, artist):
        self.playlist.splice_artist(artist)

    def next(self):
        if self.state != Player.PLAYER_STATE_STOPPED:
            self._beatplayer_stop()
        else:
            self.playlist.advance_cursor(shuffle=self.shuffle_state)
            self.song = self.playlist.get_current_playlistsong().song
            self.playlist_mode = Player.PLAYLIST_MODE_ON
    
    def next_artist(self):
        current_artist = self.song.album.artist.id 
        while self.song.album.artist.id == current_artist:
            self.playlist.advance_cursor(shuffle=self.shuffle_state)
            self.song = self.playlist.get_current_playlistsong().song
        if self.state != Player.PLAYER_STATE_STOPPED:
            self.cursor_mode = Player.CURSOR_MODE_STATIC
            self._beatplayer_stop()

# -- this probably needs to be commented before makemigrations
player = PlayerObj()
_publish_event('playlist_update', json.dumps(str(player.playlist)))

'''
             | shuffle off                 | shuffle on         |
-------------------------------------------------------------
playlist off | no play                    | any song             |
playlist on  | playlist after current     | playlist unplayed |

'''

#pi_callback = "http://%s:%s/player_complete" % (settings.BEATER_HOSTNAME, settings.BEATER_PORT)
#logger.debug("Setting callback for RPi: %s" % pi_callback)
#beatplayer_proxy.set_callback(pi_callback)

# def player(request, command, albumid=None, songid=None):
#
#     #problem = None
#     #player_info = None
#
#     #command = request.POST.get('command', None) # surprise, playlist, next, shuffle, enqueue_album, play/enqueue_song, pause, stop, mute, keep
#     #albumid = request.POST.get('albumid', None)
#     #songid = request.POST.get('songid', None)
#
#     #logger.debug("Got command: %s" % command)
#
#     _handle_command(command, albumid, songid, force_play=True)

@csrf_exempt
def playlist(request):
    global player 
    _publish_event('playlist_update', json.dumps(str(player.playlist)))
    return HttpResponse(json.dumps({'success': True}))

@csrf_exempt
def command(request, type):
    '''/command/album or /command/player'''
    response = {'result': {}, 'success': False, 'message': ""}
    
    logger.debug("command request, type: %s" % type)
    logger.debug(request.POST)
    
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

    logger.info(request.POST)
    logger.info("player_complete called with %s" % request.POST.get('success'))
    response = {'result': {}, 'success': False, 'message': ""}

    try:

        _handle_command("complete", success=request.POST.get('success'), message=request.POST.get('message'))
        response['success'] = True

    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('alert', json.dumps(response))

    return HttpResponse(json.dumps(response))

@csrf_exempt
def player_status_and_state(request):

    response = {'result': {}, 'success': False, 'message': ""}

    try:
        _show_player_status()
        response['success'] = True
    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('error', json.dumps(response))

    return HttpResponse(json.dumps({'success': True}))

def _album_command(request):

    album = Album.objects.get(pk=request.POST.get('albumid'))
    command = request.POST.get('command')

    if command == "keep":

        album.action = Album.DONOTHING
        album.save()
        response['albumid'] = album.id

def _handle_command(command, **kwargs): #albumid=None, songid=None, artistid=None, success=True, message='', force_play=True):

    global player

    '''
    how do we want playback to behave?
        keep a playlist with a cursor (current)
        keep a player model that holds one song at a time
        user controls how and when the cursor moves and when songs are loaded
    * remove 'playlist' button - player is 'on', except when immediate commands are given
    'playlist'
        - is sticky on or off, even when stopped
        - once on, only goes to off when:
            - a single song is played
            - effectively, playing a single song is the same as splice + next, but without actually adding the song to the playlist
        - once off, goes to on when:
            - song completes
            - 'next'
    'complete'
        - if playing, turns on playlist and picks up at cursor
        - if stopped, does nothing (only happens when already stopped and a single song is played)
        - should never be paused
    'enqueue' tacks song or album onto the end, no effect on playback
    'splice' sticks song or album in the middle, no effect on playback
    'play song'
        - if playing or paused:
            - if on playlist, advances cursor to next song (preference?), turns off playlist, issues call for this song (don't add to playlist)
            - if off playlist, issues call for this song (don't add to playlist)
        - if stopped, issues call for this song (don't add to playlist)
            - call includes callback tag for 'that was a single play, don't continue playing anything else'
            - or add a fourth state 'waiting to be stopped when complete'
    'play album'
        - splice album in, advance cursor
        - for simplicity, this is actually 'splice album', there's no such thing as 'play album aside from playlist'
    'stop'
        - stops playback, leave cursor (preference?) and playlist on or off
        - keep current song in player
    'play'
        - if stopped and song in player, issues call for song
        - if stopped and no song in player
            - turns on playlist, issues call for song at cursor
        - if playing, does nothing
        - if paused, unpause
    'pause'
        - if playing, pause
        - if paused, play
        - if stopped, nothing
    'next'
        - if off playlist, turns on playlist
        - else advances cursor
        - loads song at cursor
        - if playing, issues play
    future:
        - implement shuffle
        - implement 'side play' for playing albums without affecting playlist
        - preferences:
            - auto play on next
            - auto advance
    '''
    
        
    if command == 'complete':
        player.call(command, success=kwargs['success']=='True', message=kwargs['message'])
    else:
        player.call(command, **kwargs)
    # if command == "player_complete":
    #     player.complete()
    # elif command == "next":
    #     player.next()
    # elif command == "shuffle":
    #     player.toggle_shuffle()
    # elif command == "play":
    #     if song:
    #         player.play_song(song)
    #     elif album:
    #         player.play_album(album)
    #     else:
    #         player.play()
    # elif command == "enqueue":
    #     if song:
    #         self.playlist.add_song(song)
    #     elif album:
    #         self.playlist.add_album(album)
    # elif command == "pause":
    #     player.pause()
    # elif command == "stop":
    #     player.stop()
    # elif command == "mute":
    #     player.mute()
    
    return HttpResponse(json.dumps({'success': True}))


def _show_player_status():
    global player
    _publish_event('player_status', json.dumps({'player': {'shuffle': player.shuffle_state, 'mute': player.mute_state}, 'current_song': render_to_string('_current_song.html', {'song': player.song})}))

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

    return "%s/%s/%s/%s" % (beatplayer_music_folder, song.album.artist.name, song.album.name, song.name)


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
