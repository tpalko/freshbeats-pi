from django.conf import settings
from django.template.loader import render_to_string
import threading
from contextlib import contextmanager 
from ..models import Album, Artist, Player
from xmlrpc import client
import logging
import json
from ..common.switchboard import _publish_event
from .playlist import Playlist 
from .health import BeatplayerRegistrar

logger = logging.getLogger(__name__)

DEFAULT_MUTE = False 
DEFAULT_SHUFFLE = False
DEFAULT_STATE= Player.PLAYER_STATE_STOPPED
DEFAULT_CURSOR_MODE = Player.CURSOR_MODE_NEXT
DEFAULT_REPEAT_SONG = False 
DEFAULT_VOLUME = 90

class PlayerWrapper():
    '''
    Player implements standard playback actions with a Playlist and additional logic and state.
    '''
    
    playlist = None
    beatplayer_client = None 
    
    __instance = None 
    lock = None 
    
    @staticmethod
    def getInstance():
        if PlayerWrapper.__instance == None:
            PlayerWrapper()
        return PlayerWrapper.__instance 
        
    def __init__(self, *args, **kwargs):
        if PlayerWrapper.__instance != None:
            raise Exception("Call PlayerWrapper.getInstance() for singleton")
        else:
            self.lock = threading.Lock()
            self.playlist = Playlist()
            self.beatplayer_client = client.ServerProxy(settings.BEATPLAYER_URL)
            PlayerWrapper.__instance = self 
    
    @contextmanager
    def player(self, read_only=False, command=None, args=None):
        if read_only:
            player = self._get_last()
            logger.debug("Player state (r/o yield): %s" % player.status_dump())
            try:
                yield player
            except:
                pass 
        else:
            self.lock.acquire()
            player = self._get_last()
            logger.debug("Player state (r/w yield): %s" % player.status_dump())
            try:
                yield player
            finally:
                player.preceding_command = command 
                player.preceding_command_args = args
                
                player.playlistsong = self.playlist.get_current_playlistsong()
                
                beatplayer = BeatplayerRegistrar.getInstance()
                with beatplayer.client_state(read_only=True) as client_state:
                    player.beatplayer_status = client_state.status
                    player.beatplayer_registered = client_state.registered
                
                last_player = self._get_last()
                
                if(not player.compare(last_player)):
                    logger.info("Player state (save): %s" % player.status_dump())
                    player.save()
                self.lock.release()
    
    # def _load(self):         
    #     player = self._get_last()
    #     if player:
    #         self.mute = player.mute
    #         self.shuffle = player.shuffle
    #         self.state = player.state
    #         self.cursor_mode = player.cursor_mode
    #         self.repeat_song = player.repeat_song
    #         self.volume = player.volume
    #     else:
    #         self.mute = DEFAULT_MUTE 
    #         self.shuffle = DEFAULT_SHUFFLE
    #         self.state = DEFAULT_STATE 
    #         self.cursor_mode = DEFAULT_CURSOR_MODE
    #         self.repeat_song = DEFAULT_REPEAT_SONG
    #         self.volume = DEFAULT_VOLUME
            
    # def _save(self, player, command=None, args=None):
    #     # select p.created_at, preceding_command, preceding_command_args, beatplayer_registered, beatplayer_status, s.name, volume, mute, shuffle, state, cursor_mode, repeat_song from beater_player p left join beater_playlistsong ps on ps.id = p.playlistsong_id left join beater_song s on s.id = ps.song_id order by created_at desc limit 20;
    #     # player = Player()
    #     # players = Player.objects.all()
    #     # if len(players) > 0:
    #     #     player = players[0]        
    # 
    #     # player.mute = self.mute
    #     # player.shuffle = self.shuffle
    #     # player.state = self.state
    #     # player.cursor_mode = self.cursor_mode
    #     # player.repeat_song = self.repeat_song 
    #     # player.volume = self.volume
    # 
    #     # -- these bits are dynamic, we store for posterity not functionality 
    #     player.preceding_command = command 
    #     player.preceding_command_args = args
    # 
    #     player.playlistsong = self.playlist.get_current_playlistsong()
    # 
    #     beatplayer = BeatplayerRegistrar.getInstance()
    #     with beatplayer.client_state(read_only=True) as client_state:
    #         player.beatplayer_status = client_state.status
    #         player.beatplayer_registered = client_state.registered
    # 
    #     last_player = self._get_last()
    # 
    #     if(not player.compare(last_player)):
    #         player.save()
    
    def _get_last(self):
        player = Player.objects.all().order_by('-created_at').first()
        if not player:
            player = Player()
            player.mute = DEFAULT_MUTE 
            player.shuffle = DEFAULT_SHUFFLE
            player.state = DEFAULT_STATE 
            player.cursor_mode = DEFAULT_CURSOR_MODE
            player.repeat_song = DEFAULT_REPEAT_SONG
            player.volume = DEFAULT_VOLUME
            player.save()
        return player
    
    def _vals(self):
        return { k: self.__dict__[k] for k in self.__dict__.keys() if type(self.__dict__[k]).__name__ in ['str','bool','int'] }
        
    def call(self, command, **kwargs):
        
        logger.debug("handling player call - %s, kwargs: %s" % (command, json.dumps(kwargs)))
        
        f = self.__getattribute__(command)
        response = f(**{ k: kwargs[k] for k in kwargs if kwargs[k] is not None})
            
        if response:
            logger.debug("(call) %s response: %s" % (command, response))
        if response and not response['success'] and response['message']:
            _publish_event('message', json.dumps(response['message']))
        
        #logger.debug("Saving state..")
        #self._save(command, kwargs)
        #logger.debug("Showing status..")
        self.show_player_status()
        beatplayer = BeatplayerRegistrar.getInstance()
        beatplayer.show_status()
    
    def parse_state(self, health_data):
        with self.player() as player:
            if 'ps' in health_data:
                if health_data['ps']['pid'] < 0:
                    player.state = Player.PLAYER_STATE_STOPPED
                    player.mute = False
                else:
                    player.state = Player.PLAYER_STATE_PLAYING
                    
            player.volume = health_data['volume'] if 'volume' in health_data else player.volume
            player.state = Player.PLAYER_STATE_PAUSED if 'paused' in health_data and health_data['paused'] else player.state
            player.mute = health_data['muted'] == 'True' if 'muted' in health_data else player.mute
            player.time_remaining = health_data['time_remaining'] if 'time_remaining' in health_data else 0
            player.time_pos = health_data['time_pos'] if 'time_pos' in health_data else 0
            player.percent_pos = health_data['percent_pos'] if 'percent_pos' in health_data else 0
        self.show_player_status()
        
    def get_current_song(self):
        return self.playlist.get_current_playlistsong().song
        
    # def set_volume(self, **kwargs):
    #     with self.player() as player:
    #         player.volume = kwargs['volume'] if 'volume' in kwargs else player.volume
        
    # def clear_state(self, state=None):
    #     with self.player() as player:
    
    def complete(self, success=True, message=''):   
        response = {'success': False, 'message': ''}
        with self.player() as player:
            if not success:
                #player.state = Player.PLAYER_STATE_STOPPED
                response['message'] = message 
            else:
                if player.state != Player.PLAYER_STATE_STOPPED:
                    if player.cursor_mode == Player.CURSOR_MODE_NEXT:
                        #cursor_set = self.playlist.advance_cursor(shuffle=player.shuffle)
                        pass 
                    else:
                        player.cursor_mode = Player.CURSOR_MODE_NEXT
                    #response = self._beatplayer_play()
                    if response['success']:
                        player.state = Player.PLAYER_STATE_PLAYING
                else:
                    response['success'] = True 
        return response 
    
    def show_player_status(self):
        #logger.info("Rendering current song..")
        current_song_html = render_to_string('_current_song.html', {'song': self.get_current_song()})
        #logger.info("Stringing playlist..")
        playlist = str(self.playlist)
        #logger.info("stringed")        
        player_dump = {}
        with self.player(read_only=True) as player:
            player_dump = { k: str(player.__getattribute__(k)) for k in ['shuffle', 'mute', 'state', 'volume', 'time_remaining', 'time_pos', 'percent_pos'] }
        _publish_event('player_status', json.dumps({'player': player_dump, 'current_song': current_song_html, 'playlist': playlist}))
        
    ## -- BEGIN CLIENT CALLS -- ## 
    
    def _beatplayer_play(self):
        song = self.playlist.get_current_playlistsong().song        
        song_filepath = "%s/%s/%s" % (song.album.artist.name, song.album.name, song.name)
        callback = "http://%s:%s/player_complete/" % (settings.FRESHBEATS_CALLBACK_HOST, settings.FRESHBEATS_CALLBACK_PORT)
        logger.info("Calling beatplayer. song: %s callback: %s" % (song_filepath, callback))
        response = self.beatplayer_client.play(song_filepath, callback)
        logger.debug("play response: %s" % json.dumps(response))
        if response['success']:
            self.playlist.increment_current_playlistsong_play_count()
        return response 
        
    def _beatplayer_stop(self):
        response = self.beatplayer_client.stop()
        logger.debug("(_beatplayer_stop) stop response: %s" % json.dumps(response))
        return response
    
    def _beatplayer_mute(self):
        return self.beatplayer_client.mute()
        
    def _beatplayer_pause(self):
        return self.beatplayer_client.pause()
    
    def _beatplayer_volume_down(self):
        return self.beatplayer_client.volume_down()
    
    def _beatplayer_volume_up(self):
        return self.beatplayer_client.volume_up()
    
    ## -- END CLIENT CALLS -- ##
    
    ## -- BEGIN UI BUTTONS -- ## 
    
    def toggle_mute(self, **kwargs):
        response = self._beatplayer_mute()
        if response['success']:
            with self.player() as player:
                player.mute = not player.mute
        return response 
    
    def pause(self, **kwargs):
        response = None 
        with self.player() as player:
            if player.state == Player.PLAYER_STATE_PAUSED:
                response = self._beatplayer_pause()
                if response['success']:
                    player.state = Player.PLAYER_STATE_PLAYING
            elif player.state == Player.PLAYER_STATE_PLAYING:
                response = self._beatplayer_pause()
                if response['success']:
                    player.state = Player.PLAYER_STATE_PAUSED
        return response 
    
    def previous(self, **kwargs):
        response = None 
        with self.player(read_only=True) as player:
            self.playlist.back_up_cursor()
            if player.state != Player.PLAYER_STATE_STOPPED:
                self._beatplayer_play()
        return response 
    
    def restart(self, **kwargs):
        response = None 
        with self.player(read_only=True) as player:
            if player.state != Player.PLAYER_STATE_STOPPED:
                self._beatplayer_play()
        return response 
    
    def stop(self, **kwargs):
        response = None 
        with self.player() as player:
            if player.state != Player.PLAYER_STATE_STOPPED:
                response = self._beatplayer_stop()
                logger.debug("_beatplayer_stop response: %s" % response)
                if response['success'] or 'Broken pipe' in response['message'] or 'no beatplayer process' in response['message']:
                    logger.debug("(stop) stop response: %s" % response)
                    player.state = Player.PLAYER_STATE_STOPPED
                else:
                    logger.debug("called stop, but did not set state to stopped for some reason")
        return response
        
    # -- play_song and play_album are both 'off playlist' operations
    # -- but there's currently no such thing as 'off playlist'
    # -- play_song can do it, because it's only one song, and we can trigger state change on complete or next 
    # -- play_album can't do that, so we splice it
    
    def _advance_play(self, player):
        player.shuffle = False 
        self.playlist.advance_cursor(shuffle=player.shuffle)
        response = self._beatplayer_play()
        if response['success']:
            player.state = Player.PLAYER_STATE_PLAYING   
            
    def play(self, **kwargs):
        song = None 
        album = None 
        artist = None 
        response = None
        with self.player() as player:            
            if 'songid' in kwargs and kwargs['songid'] is not None:  
                songid = kwargs['songid']
                song = Song.objects.get(pk=songid)
                self.playlist.splice_song(song)
                self._advance_play(player)             
            elif 'albumid' in kwargs and kwargs['albumid'] is not None:
                albumid = kwargs['albumid']
                album = Album.objects.get(pk=albumid)
                self.playlist.splice_album(album)
                self._advance_play(player)
            elif 'artistid' in kwargs and kwargs['artistid'] is not None:
                artistid = kwargs['artistid']
                artist = Artist.objects.get(pk=artistid)
                self.playlist.splice_artist(artist)
                self._advance_play(player)
            elif 'playlistsongid' in kwargs and kwargs['playlistsongid'] is not None:
                self.playlist.advance_cursor(kwargs['playlistsongid'])
                response = self._beatplayer_play()
                if response['success']:
                    player.state = Player.PLAYER_STATE_PLAYING                
            else:
                if player.state == Player.PLAYER_STATE_STOPPED:
                    response = self._beatplayer_play()
                elif player.state == Player.PLAYER_STATE_PAUSED:
                    response = self._beatplayer_pause()
                if response and response['success']:
                    player.state = Player.PLAYER_STATE_PLAYING
        return response
    
    def next(self, **kwargs):
        response = None 
        with self.player(read_only=True) as player:
            cursor_set = self.playlist.advance_cursor(shuffle=player.shuffle)
            if player.state != Player.PLAYER_STATE_STOPPED:
                self._beatplayer_play()
        return response 
    
    def next_artist(self, **kwargs):        
        song = self.playlist.get_current_playlistsong().song
        current_artist = song.album.artist.id 
        with self.player(read_only=True) as player:
            while song.album.artist.id == current_artist:
                cursor_set = self.playlist.advance_cursor(shuffle=player.shuffle)
                song = self.playlist.get_current_playlistsong().song
            if player.state != Player.PLAYER_STATE_STOPPED:            
                self._beatplayer_play()
    
    def toggle_shuffle(self, **kwargs):
        with self.player() as player:
            player.shuffle = not player.shuffle
        
    def toggle_repeat_song(self, **kwargs):
        with self.player() as player:
            player.repeat_song = not player.repeat_song 
        
    def volume_down(self, **kwargs):
        response = self._beatplayer_volume_down()
        #self.set_volume(volume=response['data']['volume'])
        return response
        
    def volume_up(self, **kwargs):
        response = self._beatplayer_volume_up()
        #self.set_volume(volume=response['data']['volume'])
        return response
    
    def splice(self, **kwargs):
        song = None 
        album = None 
        artist = None 
        response = None
        if 'songid' in kwargs and kwargs['songid'] is not None:  
            songid = kwargs['songid']
            song = Song.objects.get(pk=songid)
            response = self.playlist.splice_song(song)
        elif 'albumid' in kwargs and kwargs['albumid'] is not None:
            albumid = kwargs['albumid']
            album = Album.objects.get(pk=albumid)
            response = self.playlist.splice_album(album)
        elif 'artistid' in kwargs and kwargs['artistid'] is not None:
            artistid = kwargs['artistid']
            artist = Artist.objects.get(pk=artistid)
            response = self.playlist.splice_artist(artist)
        return response
    
    def enqueue(self, **kwargs):
        if 'songid' in kwargs and kwargs['songid'] is not None:  
            songid = kwargs['songid']
            song = Song.objects.get(pk=songid)
            self.playlist.add_song_to_playlist(song)
        elif 'albumid' in kwargs and kwargs['albumid'] is not None:
            albumid = kwargs['albumid']
            album = Album.objects.get(pk=albumid)
            self.playlist.add_album_to_playlist(album)
        elif 'artistid' in kwargs and kwargs['artistid'] is not None:
            artistid = kwargs['artistid']
            artist = Artist.objects.get(pk=artistid)
            self.playlist.add_artist_to_playlist(artist)

    ## -- END UI BUTTONS -- ## 
    
    
        
