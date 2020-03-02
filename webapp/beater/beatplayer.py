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
from datetime import datetime, timedelta
import threading
import re
import time
from .util import capture
from .switchboard import _publish_event

logging.basicConfig(level=logging.DEBUG, disable_existing_loggers=False)
logger = logging.getLogger(__name__)

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
    
    playlist_stale = True 
    playlist_html = None 

    def __init__(self, *args, **kwargs):
        if not self.get_current_playlistsong():
            self.set_current_playlistsong(PlaylistSong.objects.all().order_by('queue_number').first())

    def __str__(self):
        if self.playlist_stale:
            playlistsongs = PlaylistSong.objects.all().order_by('queue_number');
            self.playlist_html = render_to_string("_playlist.html", {'playlistsongs': playlistsongs})
            self.playlist_stale = False 
        return self.playlist_html
    
    def play_count_filter(self, playlistsongs):
        if len(playlistsongs) > 0:
            play_count_array = [ s.play_count for s in playlistsongs ]
            avg = sum(play_count_array) / len(play_count_array)
            logger.debug("average play count: %s" % avg)
            return playlistsongs.filter(play_count__lte=avg)
        return playlistsongs 
        
    def age_filter(self, playlistsongs):
        if len(playlistsongs) > 0:
            now = datetime.now()                
            age_array = [ 0 if not s.last_played_at else (now - s.last_played_at).seconds for s in playlistsongs ]
            avg = sum(age_array) / len(age_array)
            logger.debug("average age in seconds: %s" % avg)
            return playlistsongs.filter(Q(last_played_at__lte=(now - timedelta(seconds=avg)))|Q(last_played_at__isnull=True))
        return playlistsongs 
        
    def advance_cursor(self, playlistsongid=None, shuffle=False):

        cursor_set = False 
        new_playlistsong = None 
        
        if playlistsongid:
            new_playlistsong = PlaylistSong.objects.get(pk=playlistsongid)
        elif shuffle:
            valid_playlistsongs = PlaylistSong.objects.all()
            current_playlistsong = self.get_current_playlistsong()
            if current_playlistsong:
                valid_playlistsongs = PlaylistSong.objects.filter(~Q(queue_number=current_playlistsong.queue_number))
            logger.debug("%s valid playlistsongs" % len(valid_playlistsongs))
            new_playlistsong = random.choice(self.age_filter(self.play_count_filter(valid_playlistsongs)))
            if not new_playlistsong:
                new_playlistsong = random.choice(valid_playlistsongs)
        else:
            new_playlistsong = self._get_remaining_playlistsongs().order_by('queue_number').first()
        
        if new_playlistsong:
            self.set_current_playlistsong(new_playlistsong)
            cursor_set = True 
        
        return cursor_set
    
    def back_up_cursor(self):
        cursor_set = False 
        new_playlistsong = self._get_previous_playlistsongs().order_by('-queue_number').first()
        if new_playlistsong:
            self.set_current_playlistsong(new_playlistsong)
            cursor_set = True         
        return cursor_set
        
    def set_current_playlistsong(self, playlistsong):
        current_playlistsong = self.get_current_playlistsong()
        if current_playlistsong:
            current_playlistsong.is_current = False
            current_playlistsong.save()
        playlistsong.is_current = True
        playlistsong.save()
        self.playlist_stale = True
        
    def get_current_playlistsong(self):
        return PlaylistSong.objects.filter(is_current=True).first()
    
    def _get_previous_playlistsongs(self):
        current_playlistsong = self.get_current_playlistsong()
        if current_playlistsong:
            return PlaylistSong.objects.filter(queue_number__lt=current_playlistsong.queue_number)
        else:
            return PlaylistSong.objects.all()
            
    def _get_remaining_playlistsongs(self):
        current_playlistsong = self.get_current_playlistsong()
        if current_playlistsong:
            return PlaylistSong.objects.filter(queue_number__gt=current_playlistsong.queue_number)
        else:
            return PlaylistSong.objects.all()
        
    def increment_current_playlistsong_play_count(self):
        current_playlistsong = self.get_current_playlistsong()
        if current_playlistsong:
            current_playlistsong.play_count = current_playlistsong.play_count + 1
            current_playlistsong.last_played_at = datetime.now()
            current_playlistsong.save()
            self.playlist_stale = True

    def add_song_to_playlist(self, song, queue_number=None):
        if not queue_number:
            queue_number = PlaylistSong.objects.all().order_by('-queue_number').first().queue_number + 1
        new_playlistsong = PlaylistSong(song=song, queue_number=queue_number)
        new_playlistsong.save()
        self.playlist_stale = True 

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
            self.playlist_stale = True
        
    def splice_song(self, song):
        self._bump_remaining_playlistsongs(1)
        current_playlistsong = self.get_current_playlistsong()
        self.add_song_to_playlist(song, current_playlistsong.queue_number + 1)

    def splice_album(self, album):        
        song_count = album.song_set.count()
        self._bump_remaining_playlistsongs(song_count)
        # -- splice in the album as the next queue numbers 
        current_playlistsong = self.get_current_playlistsong()
        for i, song in enumerate(album.song_set.all(), 1):
            self.add_song_to_playlist(song, current_playlistsong.queue_number + i)

    def splice_artist(self, artist):
        song_count = sum([ album.song_set.count() for album in artist.album_set.all() ])
        self._bump_remaining_playlistsongs(song_count)
        bump = 0
        current_playlistsong = self.get_current_playlistsong()
        for i, album in enumerate(artist.album_set.all(), 1):
            for j, song, in enumerate(album.song_set.all(), 1):
                bump = bump + 1
                self.add_song_to_playlist(song, current_playlistsong.queue_number + bump)

BEATPLAYER_STATUS_UP = 'up'
BEATPLAYER_STATUS_DOWN = 'down'

class Beatplayer():
    
    client = None 
    beater_url = None 
    status = BEATPLAYER_STATUS_DOWN
    last_status = None 
    volume = None 
    registered = False 
    
    def __init__(self, *args, **kwargs):
        if 'url' not in kwargs:
            raise Exception("Beatplayer requires url")
        self.beater_url = kwargs['url']
        logger.debug("Creating beatplayer @ %s" % self.beater_url)
        self.client = client.ServerProxy(self.beater_url)
        
    def register(self, callback_url):
        def register_client():
            logger.debug("Attempting to register with %s" % self.beater_url)
            attempts = 0
            while not self.registered:
                logger.info("Registration attempting..")
                try:
                    attempts += 1
                    response = self.client.register_client(callback_url)
                    self.registered = response['data']['registered']
                    if self.registered:
                        logger.info("Application subscribed to beatplayer! (%s attempts)" % attempts)                        
                        self.last_status = datetime.now()
                    else:
                        logger.debug("attempt %s - not yet registered: %s" % (attempts, response))
                    _show_beatplayer_status()
                    if response['data']['retry'] == False:
                        break
                except:
                    logger.error("Error registering with %s: %s" % (self.beater_url, str(sys.exc_info()[1])))
                wait = attempts*3 if attempts < 200 else 600
                logger.debug("%s attempts, waiting %s.." % (attempts, wait))
                time.sleep(wait)
            if self.registered:
                t = threading.Thread(target=fresh_check)
                t.start()
        def fresh_check():
            misses = 0
            while self.registered:
                logger.debug("Fresh checking..")
                if self.last_status is None:
                    misses += 1
                    logger.warn("No beatplayer report: %s/3" % misses)
                    if misses > 2:
                        break 
                elif self.last_status < datetime.now() - timedelta(seconds=30):
                    logger.warn("Beatplayer down for 30 seconds, assuming restart, quitting fresh check and attempting re-registration")
                    break
                elif self.last_status < datetime.now() - timedelta(seconds=15):
                    self.status = BEATPLAYER_STATUS_DOWN
                    logger.warn("Stale status - beatplayer is %s" % self.status)
                    _show_beatplayer_status()
                time.sleep(5)
            logger.warn("Self-deregistering..")
            self.registered = False          
            _show_beatplayer_status()           
            t = threading.Thread(target=register_client)
            t.start()
                    
        t = threading.Thread(target=register_client)
        t.start()
            
class PlayerObj():
    '''
    Player implements standard playback actions with a Playlist and additional logic and state.
    '''
    
    mute = False
    shuffle = False
    repeat_song = False 
    
    state = Player.PLAYER_STATE_STOPPED
    cursor_mode = Player.CURSOR_MODE_NEXT
    
    playlist = None
    beatplayer = None 
    
    def __init__(self, *args, **kwargs):
        self._load()
        self.playlist = Playlist()
        self.beatplayer = Beatplayer(url=settings.BEATPLAYER_URL)

    def get_current_song(self):
        return self.playlist.get_current_playlistsong().song
        
    def _beatplayer_play(self):
        song = self.playlist.get_current_playlistsong().song        
        beatplayer_music_folder = self.beatplayer.client.get_music_folder()
        song_filepath = "%s/%s/%s/%s" % (beatplayer_music_folder, song.album.artist.name, song.album.name, song.name)
        callback = "http://%s:%s/player_complete/" % (settings.FRESHBEATS_CALLBACK_HOST, settings.FRESHBEATS_CALLBACK_PORT)
        logger.info("calling beatplayer. song: %s callback: %s" % (song_filepath, callback))
        response = self.beatplayer.client.play(song_filepath, callback)
        logger.debug("play response: %s" % json.dumps(response))
        if response['success']:
            self.playlist.increment_current_playlistsong_play_count()
        return response 
        
    def _beatplayer_stop(self):
        response = self.beatplayer.client.stop()
        logger.debug("stop response: %s" % json.dumps(response))
        return response
    
    def _beatplayer_mute(self):
        return self.beatplayer.client.mute()
        
    def _beatplayer_pause(self):
        return self.beatplayer.client.pause()
    
    def _beatplayer_volume_down(self):
        return self.beatplayer.client.volume_down()
    
    def _beatplayer_volume_up(self):
        return self.beatplayer.client.volume_up()
    
    def _load(self):
        players = Player.objects.all()
        if len(players) > 0:
            player = players[0]
            self.mute = player.mute
            self.shuffle = player.shuffle
            self.state = player.state
            self.cursor_mode = player.cursor_mode
            
    def _save(self):
        player = Player()
        players = Player.objects.all()
        if len(players) > 0:
            player = players[0]        
        player.mute = self.mute
        player.shuffle = self.shuffle
        player.state = self.state
        player.cursor_mode = self.cursor_mode
        player.save()
    
    def _vals(self):
        return { k: self.__dict__[k] for k in self.__dict__.keys() if type(self.__dict__[k]).__name__ in ['str','bool','int'] }
        
    def call(self, command, **kwargs):
        
        logger.debug("handling player call - %s, kwargs: %s" % (command, json.dumps(kwargs)))
        logger.debug(self._vals())
            
        f = self.__getattribute__(command)
        response = f(**{ k: kwargs[k] for k in kwargs if kwargs[k] is not None})
        if response:
            logger.debug("%s response: %s" % (command, response))
        if response and not response['success'] and response['message']:
            _publish_event('message', json.dumps(response['message']))
        
        #logger.debug("Saving state..")
        self._save()
        #logger.debug("Showing status..")
        _show_player_status(self)
        
    def clear_state(self, state=None):
        self.state = Player.PLAYER_STATE_STOPPED
        self.mute = False         
    
    def complete(self, success=True, message=''):   
        response = {'success': False, 'message': ''}
        if not success:
            self.state = Player.PLAYER_STATE_STOPPED
            response['message'] = message 
        else:
            if self.state != Player.PLAYER_STATE_STOPPED:
                if self.cursor_mode == Player.CURSOR_MODE_NEXT:
                    cursor_set = self.playlist.advance_cursor(shuffle=self.shuffle)
                else:
                    self.cursor_mode = Player.CURSOR_MODE_NEXT
                response = self._beatplayer_play()
                if response['success']:
                    self.state = Player.PLAYER_STATE_PLAYING
            else:
                response['success'] = True 
        return response 
        
    def toggle_shuffle(self, **kwargs):
        self.shuffle = not self.shuffle
    
    def toggle_mute(self, **kwargs):
        response = self._beatplayer_mute()
        if response['success']:
            self.mute = not self.mute
        return response 
    
    def toggle_repeat_song(self, **kwargs):
        self.repeat_song = not self.repeat_song 
    
    def previous(self, **kwargs):
        response = None 
        self.playlist.back_up_cursor()
        if self.state != Player.PLAYER_STATE_STOPPED:
            self.cursor_mode = Player.CURSOR_MODE_STATIC
            response = self._beatplayer_stop()
        return response 
    
    def restart(self, **kwargs):
        response = None 
        if self.state != Player.PLAYER_STATE_STOPPED:
            self.cursor_mode = Player.CURSOR_MODE_STATIC
            response = self._beatplayer_stop()
        return response 
    
    def volume_down(self, **kwargs):
        response = self._beatplayer_volume_down()
        #self.set_beatplayer_volume(volume=response['data']['volume'])
        return response
        
    def volume_up(self, **kwargs):
        response = self._beatplayer_volume_up()
        #self.set_beatplayer_volume(volume=response['data']['volume'])
        return response
    
    def set_beatplayer_volume(self, **kwargs):
        self.beatplayer.volume = kwargs['volume'] if 'volume' in kwargs else self.beatplayer.volume

    def pause(self, **kwargs):
        response = None 
        if self.state == Player.PLAYER_STATE_PAUSED:
            response = self._beatplayer_pause()
            if response['success']:
                self.state = Player.PLAYER_STATE_PLAYING
        elif self.state == Player.PLAYER_STATE_PLAYING:
            response = self._beatplayer_pause()
            if response['success']:
                self.state = Player.PLAYER_STATE_PAUSED
        return response 
    
    def stop(self, **kwargs):
        response = None 
        if self.state != Player.PLAYER_STATE_STOPPED:
            response = self._beatplayer_stop()
            if response['success'] or 'Broken pipe' in response['message'] or 'no beatplayer process' in response['message']:
                self.state = Player.PLAYER_STATE_STOPPED
        return response
            
    def play(self, **kwargs):
        song = None 
        album = None 
        artist = None 
        response = None
        if 'songid' in kwargs and kwargs['songid'] is not None:  
            songid = kwargs['songid']
            song = Song.objects.get(pk=songid)
            response = self._play_song(song)
        elif 'albumid' in kwargs and kwargs['albumid'] is not None:
            albumid = kwargs['albumid']
            album = Album.objects.get(pk=albumid)
            response = self._play_album(album)
        elif 'artistid' in kwargs and kwargs['artistid'] is not None:
            artistid = kwargs['artistid']
            artist = Artist.objects.get(pk=artistid)
            response = self._play_artist(artist)
        elif 'playlistsongid' in kwargs and kwargs['playlistsongid'] is not None:
            self.playlist.advance_cursor(kwargs['playlistsongid'])
            if self.state != Player.PLAYER_STATE_STOPPED:            
                self.cursor_mode = Player.CURSOR_MODE_STATIC
                self._beatplayer_stop()
            else:
                response = self._beatplayer_play()
                if response['success']:
                    self.state = Player.PLAYER_STATE_PLAYING
        else:
            if self.state == Player.PLAYER_STATE_STOPPED:
                response = self._beatplayer_play()
            elif self.state == Player.PLAYER_STATE_PAUSED:
                response = self._beatplayer_pause()
            if response and response['success']:
                self.state = Player.PLAYER_STATE_PLAYING
        return response
    
    def splice(self, **kwargs):
        song = None 
        album = None 
        artist = None 
        response = None
        if 'songid' in kwargs and kwargs['songid'] is not None:  
            songid = kwargs['songid']
            song = Song.objects.get(pk=songid)
            response = self.splice_song(song)
        elif 'albumid' in kwargs and kwargs['albumid'] is not None:
            albumid = kwargs['albumid']
            album = Album.objects.get(pk=albumid)
            response = self.splice_album(album)
        elif 'artistid' in kwargs and kwargs['artistid'] is not None:
            artistid = kwargs['artistid']
            artist = Artist.objects.get(pk=artistid)
            response = self.splice_artist(artist)
        return response
    
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
        response = None 
        self.shuffle = False 
        self.splice_song(song)
        if self.state != Player.PLAYER_STATE_STOPPED:
            response = self._beatplayer_stop()
        else:
            cursor_set = self.playlist.advance_cursor(shuffle=self.shuffle)
            response = self._beatplayer_play()
            if response['success']:
                self.state = Player.PLAYER_STATE_PLAYING
        return response 
        
    def _play_album(self, album):
        # -- instead of splice, this should work with a 'side playlist'
        response = None 
        self.shuffle = False 
        self.splice_album(album)
        if self.state != Player.PLAYER_STATE_STOPPED:
            response = self._beatplayer_stop()
        else:
            cursor_set = self.playlist.advance_cursor(shuffle=self.shuffle)
            response = self._beatplayer_play()            
            if response['success']:
                self.state = Player.PLAYER_STATE_PLAYING
        return response 

    def _play_artist(self, artist):
        # -- instead of splice, this should work with a 'side playlist'
        response = None 
        self.shuffle = False 
        self.splice_artist(artist)
        if self.state != Player.PLAYER_STATE_STOPPED:
            response = self._beatplayer_stop()
        else:
            cursor_set = self.playlist.advance_cursor(shuffle=self.shuffle)
            response = self._beatplayer_play()            
            if response['success']:
                self.state = Player.PLAYER_STATE_PLAYING
        return response 
            
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

    def next(self, **kwargs):
        response = None 
        if self.state != Player.PLAYER_STATE_STOPPED:
            response = self._beatplayer_stop()
        else:
            cursor_set = self.playlist.advance_cursor(shuffle=self.shuffle)
        return response 
    
    def next_artist(self, **kwargs):
        song = self.playlist.get_current_playlistsong().song
        current_artist = song.album.artist.id 
        while song.album.artist.id == current_artist:
            cursor_set = self.playlist.advance_cursor(shuffle=self.shuffle)
            song = self.playlist.get_current_playlistsong().song
        if self.state != Player.PLAYER_STATE_STOPPED:            
            self.cursor_mode = Player.CURSOR_MODE_STATIC
            self._beatplayer_stop()

# TODO: this needs to be reimplemented
# -- beatplayer up first, webapp calls on start to register, beatplayer pings on short cycle, webapp checks age of last ping for status 
# -- webapp up first, exponential backoff call to beatplayer to register with some high max, refresh backoff on page requests 
logger.info("")
logger.info("*********************************")
logger.info("* Starting up global beatplayer *")
logger.info("*********************************")
logger.info("")
beatplayer = Beatplayer(url=settings.BEATPLAYER_URL)
beatplayer.register("http://%s:%s/health_response/" % (settings.FRESHBEATS_CALLBACK_HOST, settings.FRESHBEATS_CALLBACK_PORT))

@csrf_exempt
def health_response(request):
    
    health = json.loads(request.body.decode())
    
    if not health['success'] and health['message'] and len(health['message']) > 0:
        _publish_event('message', json.dumps(health['message']))
        
    health_data = health['data']
    player = PlayerObj()
    if 'ps' in health_data and health_data['ps']['pid'] < 0:
        player.call("clear_state")
    player.call('set_beatplayer_volume', volume=health_data['volume'])  
    
    global beatplayer 
    if beatplayer.status != BEATPLAYER_STATUS_UP:
        logger.info("beatplayer status: %s -> %s" % (beatplayer.status, BEATPLAYER_STATUS_UP))
        beatplayer.status = BEATPLAYER_STATUS_UP
        _show_beatplayer_status()
    beatplayer.last_status = datetime.now()

    return JsonResponse({'success': True})


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
            artistid = request.POST.get('artistid', None)
            playlistsongid = request.POST.get('playlistsongid', None)
            player = PlayerObj()
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
        player = PlayerObj()
        if complete_response['data']['complete']:
            player.call("complete", success=complete_response['success'], message=complete_response['message'])
        else:
            logger.debug("player output: %s" % complete_response['message'])
            _publish_event('player_output', json.dumps(complete_response['message']))
        response['success'] = True

    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('alert', json.dumps(response))

    return JsonResponse(response)

@csrf_exempt
def beatplayer_status(request):
    
    response = {'result': {}, 'success': False, 'message': ""}

    try:
        global beatplayer 
        _show_beatplayer_status()        
        response['success'] = True
    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('message', json.dumps(response['message']))

    return JsonResponse({'success': True})

@csrf_exempt
def player_status_and_state(request):

    response = {'result': {}, 'success': False, 'message': ""}

    try:
        player = PlayerObj()
        _show_player_status(player)        
        response['success'] = True
    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        _publish_event('message', json.dumps(response['message']))

    return JsonResponse({'success': True})

def _album_command(request):

    album = Album.objects.get(pk=request.POST.get('albumid'))
    command = request.POST.get('command')

    if command == "keep":

        album.action = Album.DONOTHING
        album.save()
        response['albumid'] = album.id

def _handle_command(command, **kwargs): #albumid=None, songid=None, artistid=None, success=True, message='', force_play=True):
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
    return JsonResponse({'success': True})


def _show_beatplayer_status():
    global beatplayer
    _publish_event('beatplayer_status', json.dumps({'status': beatplayer.status, 'registered': beatplayer.registered}))

def _show_player_status(player):    
    #logger.info("Rendering current song..")
    current_song_html = render_to_string('_current_song.html', {'song': player.get_current_song()})
    #logger.info("Stringing playlist..")
    playlist = str(player.playlist)
    #logger.info("stringed")
    _publish_event('player_status', json.dumps({'player': player._vals(), 'current_song': current_song_html, 'playlist': playlist}))

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
