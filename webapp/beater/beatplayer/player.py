import sys
import logging
import json
import math
import traceback 
import threading
from xmlrpc import client
from contextlib import contextmanager 
from django.conf import settings
from django.template.loader import render_to_string
from ..models import Album, Artist, Player, Device, Song
from ..common.switchboard import _publish_event, _get_switchboard_connection_id_for_device_id, _get_playlist_id_for_switchboard_connection_id
from .playlist import Playlist, PlaylistHelper
from .health import BeatplayerRegistrar

# -- beater.beatplayer.player
print(f'LOGGING: {__name__}')

logger = logging.getLogger(__name__)

DEFAULT_MUTE = False 
DEFAULT_SHUFFLE = False
DEFAULT_STATE = Player.PLAYER_STATE_STOPPED
DEFAULT_CURSOR_MODE = Player.CURSOR_MODE_NEXT
DEFAULT_REPEAT_SONG = False 
DEFAULT_VOLUME = 90

class PlayerWrapper():
    '''
    Player implements standard playback actions with a Playlist and additional logic and state.
    '''
    
    player_lock = None 
    device_id = None
    beatplayer_client = None 
    playlist_id = None 
    
    __instances = {}
    playlist_locks = {}
    
    @staticmethod
    def getInstance(device_id):
        if device_id not in PlayerWrapper.__instances or PlayerWrapper.__instances[device_id] == None:
            PlayerWrapper(device_id=device_id)
        return PlayerWrapper.__instances[device_id] 
        
    def __init__(self, *args, **kwargs):
        if kwargs['device_id'] in PlayerWrapper.__instances and PlayerWrapper.__instances[kwargs['device_id']] != None:
            raise Exception("Call PlayerWrapper.getInstance() for singleton")
        else:
            self.player_lock = threading.Lock()
            self.device_id = kwargs['device_id']
            with self.player(read_only=True) as player:
                if not player:
                    logger.warning("There are no players for this device")
                else:
                    self.beatplayer_client = client.ServerProxy(player.device.agent_base_url, allow_none=True)
            PlayerWrapper.__instances[self.device_id] = self 
        
    @contextmanager     
    def playlist_context(self, playlist_id):
        if playlist_id not in PlayerWrapper.playlist_locks:
            logger.debug("Creating lock for playlist %s" % (playlist_id))
            PlayerWrapper.playlist_locks[playlist_id] = threading.Lock()
        logger.debug("Wanting playlist lock %s" % playlist_id)
        # TODO: implement playlist read-only mode and avoid acquring the lock when not necessary 
        PlayerWrapper.playlist_locks[playlist_id].acquire()
        logger.debug("Acquired playlist lock %s" % playlist_id)
        playlist = Playlist.getInstance(playlist_id)
        try:
            yield playlist
        except:
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
        finally:
            playlist._renumber_playlistsong_queue()
            PlayerWrapper.playlist_locks[playlist_id].release()
            logger.debug("Released playlist lock %s" % playlist_id)
            
    @contextmanager
    def player(self, read_only=False, playlist_id=None):
        '''
        The read-only context DOES NOT PROVIDE self.playlist 
        '''
        if read_only:
            player = self._get_device_player(read_only=True)
            #logger.debug("Player state (R/O - yield): %s" % player.status_dump())
            yield player
        else:
            # -- File "/media/storage/development/github.com/freshbeats-pi/webapp/beater/beatplayer/player.py", line 170, in parse_state
            caller = traceback.format_stack()[-3].split(' ')[7].replace('\n', '')
            logger.debug("%s wants to acquire player record lock.." % caller)
            self.player_lock.acquire()
            logger.debug("%s has acquired player record lock" % caller)
            player = self._get_device_player()
            logger.debug("Player state (R/W - yield): %s" % player.status_dump())
            try:
                if playlist_id is None:
                    if player.playlistsong is not None:
                        playlist_id = player.playlistsong.playlist.id
                        logger.warning("Player %s context given no playlist ID, inferring %s from current position %s" % (player.id, playlist_id, player.playlistsong.id))
                    else:
                        logger.warning("Player %s context given no playlist ID, and player has no current position from which to infer" % player.id)
                else:
                    logger.debug("Player %s context given playlist ID %s" % (player.id, playlist_id))
                with self.playlist_context(playlist_id=playlist_id) as playlist:                    
                    self.playlist = playlist
                    logger.debug("Yielding player %s / playlist %s" % (player.id, playlist_id))
                    yield player
                
                logger.debug("Player yield returned from %s, cleaning up and saving" % caller)
                
                beatplayer = BeatplayerRegistrar.getInstance(player.device.agent_base_url)
                with beatplayer.devicehealth() as health:
                    player.beatplayer_status = health.status
                    player.beatplayer_registered_at = health.registered_at
                player.save()
                
            finally:
                #logger.debug("Player state (R/W - not saving)")
                self.player_lock.release()
                #logger.debug("Caller %s released lock" % caller)
                
            self.show_player_status()
    
    def _get_device_player(self, read_only=False):
        '''
        The player wrapper is requested by device ID.
        There is presumably a Player record behind the Device record, which is where the device left off last time, its current state.
        That's what we want. Not the very last Player record, which may have nothing to do with our device.
        But a new device would not have a relationship, or player state. 
        So by default we give it the very last Player record, a bit arbitrarily.
        If the incoming command sends it off in a completely new direction, so be it. We'll capture that state after this.
        '''
        
        device_player = None 
        
        lookupdevice = Device.objects.get(pk=self.device_id)
        beatplayer = BeatplayerRegistrar.getInstance(agent_base_url=lookupdevice.agent_base_url)
        with beatplayer.device() as device:                
            if device.player:
                logger.debug("Device %s found with player %s" % (device.id, device.player.id))
            else:
                if read_only:
                    logger.warning("Device %s had no player association, but in a read-only context so making no changes." % device.id)
                else:
                    device.player = Player.objects.order_by('-created_at').first()
                    if device.player is not None:
                        logger.info("Device %s had no player association, so associated the most recent record %s." % (device.id, device.player.id))
                    else:
                        device.player = Player.objects.create(
                            mute = DEFAULT_MUTE,
                            shuffle = DEFAULT_SHUFFLE,
                            state = DEFAULT_STATE,
                            cursor_mode = DEFAULT_CURSOR_MODE,
                            repeat_song = DEFAULT_REPEAT_SONG,
                            volume = DEFAULT_VOLUME
                        )                        
                        logger.warning("Device %s had no player association, but no player records were found. Created %s and associated it." % (device.id, device.player.id))
            
            device_player = device.player 
            
        return device_player 
    
    def _vals(self):
        return { k: self.__dict__[k] for k in self.__dict__.keys() if type(self.__dict__[k]).__name__ in ['str','bool','int'] }
        
    def call(self, command, **kwargs):
        
        logger.debug("Handling player call - %s, kwargs: %s" % (command, json.dumps(kwargs)))
        
        f = self.__getattribute__(command)
        
        with self.player(playlist_id=kwargs['playlist_id']) as player:
            player.preceding_command = command 
            player.preceding_command_args = kwargs
            response = f(player=player, **{ k: kwargs[k] for k in kwargs if kwargs[k] is not None})
            
            if response:
                logger.debug("(call) %s response: %s" % (command, response))
                if not response['success'] and response['message']:
                    _publish_event('message', json.dumps(response['message']))
        
        #logger.debug("Saving state..")
        #self._save(command, kwargs)
        #logger.debug("Showing status..")
        
        # beatplayer = BeatplayerRegistrar.getInstance()
        # beatplayer.show_status()
    
    def parse_state(self, player, health_data):

        logger.debug("Parsing health data -- %s --" % player.device.agent_base_url)
        changelog = "Player changes: "
        
        to_state = Player.PLAYER_STATE_PLAYING if 'ps' in health_data and 'is_alive' in health_data['ps'] and health_data['ps']['is_alive'] else Player.PLAYER_STATE_STOPPED
        to_state = Player.PLAYER_STATE_PAUSED if 'paused' in health_data and health_data['paused'] else to_state
        
        to_mute = health_data['muted'] == 'True' if 'muted' in health_data and to_state != Player.PLAYER_STATE_STOPPED else False 
        
        if to_state == Player.PLAYER_STATE_STOPPED:
            _publish_event('clear_player_output')
            to_mute = False 
            
        to_volume = health_data['volume'] if 'volume' in health_data else player.volume
        
        if to_state != player.state:
            changelog += "state %s -> %s " % (player.state, to_state)
            player.state = to_state
        if to_volume != player.volume:
            changelog += "volume %s -> %s " % (player.volume, to_volume)
            player.volume = to_volume
        if to_mute != player.mute:
            changelog += "mute %s -> %s " % (player.mute, to_mute)
            player.mute = to_mute
        
        logger.warning(changelog)
        
        player.time_pos = health_data['time'][0] or 0
        player.time_remaining = health_data['time'][1] or 0
        total_time = player.time_pos + player.time_remaining            
        player.percent_pos = 100*player.time_pos / total_time if total_time > 0 else 0
    
    def complete(self, player, success=True, message='', data={}):   
        response = {'success': False, 'message': ''}
        if not success:
            #player.state = Player.PLAYER_STATE_STOPPED
            response['message'] = "%s (returncode: %s)" % (message, data['returncode'])
        else:
            play_response = None 
            if player.state != Player.PLAYER_STATE_STOPPED:
                play_response = self._advance_play(player)                
            if not play_response or play_response['success']:
                response['success'] = True 
            elif play_response:
                response['message'] = play_response['message']
        return response 
    
    def show_player_status(self):
        '''
        Assembles player and playlist state and emits a player_status event.
        '''
        
        with self.player(read_only=True) as player:
            # -- READ ONLY PLAYER
            connection_ids_by_device = _get_switchboard_connection_id_for_device_id()
            if self.device_id not in connection_ids_by_device:
                logger.debug("No clients for device %s, not updating status" % player.device.name)
                return 
                
            #logger.info("stringed")        
            player_dump = { k: str(player.__getattribute__(k)) for k in ['shuffle', 'mute', 'state', 'volume', 'time_remaining', 'time_pos', 'percent_pos'] }
            if player.time_pos:
                player_dump['time_pos_display'] = "%.0f:%.0f%.0f" % (math.floor(player.time_pos/60), math.floor((player.time_pos%60)/10), math.floor((player.time_pos%60)%10))
            if player.time_remaining:
                player_dump['time_remaining_display'] = "%.0f:%.0f%.0f" % (math.floor(player.time_remaining/60), math.floor((player.time_remaining%60)/10), math.floor((player.time_remaining%60)%10))
            
            current_playlistsong = player.playlistsong if player.playlistsong else None 
            
            logger.debug("Publishing player status (player %s/device %s). Current playlistsong: %s" % (player.id, player.device.id, current_playlistsong.song.name if current_playlistsong else "<no song>"))
            
            current_song_obj = {
                'song': current_playlistsong.song if current_playlistsong else None
            }            
            current_song_html = render_to_string('_current_song.html', current_song_obj)
            
            for connection_id in connection_ids_by_device[self.device_id]:
                playlist_id = _get_playlist_id_for_switchboard_connection_id(connection_id)
                logger.debug("Found playlist %s for switchboard connection ID %s" % (playlist_id, connection_id))
                playlist_data = {
                    'playlist': PlaylistHelper.playlist(playlist_id=playlist_id) if playlist_id else None,
                    'playlistsongs': PlaylistHelper.playlistsongs(playlist_id=playlist_id) if playlist_id else [], 
                    'current_playlistsong_id': current_playlistsong.id if current_playlistsong else None
                }
                playlist_html = render_to_string("_playlist.html", playlist_data)
                _publish_event(event='player_status', payload=json.dumps({'player': player_dump, 'current_song': current_song_html, 'playlist': playlist_html}), connection_id=connection_id)
        
    ## -- BEGIN CLIENT CALLS -- ## 
    
    def _beatplayer_play(self, player):        
        # -- READ ONLY PLAYER
        song = player.playlistsong.song        
        song_filepath = "%s/%s/%s" % (song.album.artist.name, song.album.name, song.name)
        logger.info("Playing. Player state: %s. Song: %s callback: %s" % (player.state, song_filepath, settings.FRESHBEATS_COMPLETE_CALLBACK_URL))
        response = self.beatplayer_client.play(song.url, song_filepath, settings.FRESHBEATS_COMPLETE_CALLBACK_URL, player.device.agent_base_url)
        logger.debug("play response: %s" % json.dumps(response))
        if response['success']:
            self.playlist.increment_current_playlistsong_play_count(player.playlistsong.id)
            player.state = Player.PLAYER_STATE_PLAYING
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
    
    def toggle_mute(self, player, **kwargs):
        response = self._beatplayer_mute()
        if response['success']:
            player.mute = not player.mute
        return response 
    
    def pause(self, player, **kwargs):
        response = None 
        if player.state == Player.PLAYER_STATE_PAUSED:
            response = self._beatplayer_pause()
            if response['success']:
                player.state = Player.PLAYER_STATE_PLAYING
        elif player.state == Player.PLAYER_STATE_PLAYING:
            response = self._beatplayer_pause()
            if response['success']:
                player.state = Player.PLAYER_STATE_PAUSED
        return response 
    
    def previous(self, player, **kwargs):
        # -- READ ONLY
        response = None 
        player.playlistsong = self.playlist.back_up_cursor(player.playlistsong)
        if player.state != Player.PLAYER_STATE_STOPPED:
            response = self._beatplayer_play(player)
        return response 
    
    def restart(self, player, **kwargs):
        # -- READ ONLY PLAYER
        response = None 
        if player.state != Player.PLAYER_STATE_STOPPED:
            response = self._beatplayer_play(player)
        return response 
    
    def stop(self, player, **kwargs):
        response = None 
        if player.state != Player.PLAYER_STATE_STOPPED:
            response = self._beatplayer_stop()
            logger.debug("_beatplayer_stop response: %s" % response)
            if not response or response['success'] or 'Broken pipe' in response['message'] or 'no beatplayer process' in response['message']:
                logger.debug("(stop) stop response: %s" % response)
                player.state = Player.PLAYER_STATE_STOPPED
            else:
                logger.debug("called stop, but did not set state to stopped for some reason")
        return response
        
    # -- play_song and play_album are both 'off playlist' operations
    # -- but there's currently no such thing as 'off playlist'
    # -- play_song can do it, because it's only one song, and we can trigger state change on complete or next 
    # -- play_album can't do that, so we splice it
    
    def _advance(self, player, playlistsongid=None):
        player.playlistsong = self.playlist.advance_cursor(current_playlistsong=player.playlistsong, to_playlistsongid=playlistsongid, shuffle=player.shuffle)
        if not player.playlistsong:
            logger.warning("Playlist advance resulted in no selection being made")
        
    def _advance_play(self, player, playlistsongid=None):
        self._advance(player, playlistsongid=playlistsongid)
        return self._beatplayer_play(player)
            
    def play(self, player, **kwargs):
        song = None 
        album = None 
        artist = None 
        response = None
        if 'songid' in kwargs and kwargs['songid'] is not None:  
            songid = kwargs['songid']
            song = Song.objects.get(pk=songid)
            self.playlist.splice_song(song, player.playlistsong)
            player.shuffle = False 
            response = self._advance_play(player)             
        elif 'albumid' in kwargs and kwargs['albumid'] is not None:
            albumid = kwargs['albumid']
            album = Album.objects.get(pk=albumid)
            self.playlist.splice_album(album, player.playlistsong)
            player.shuffle = False 
            response = self._advance_play(player)
        elif 'artistid' in kwargs and kwargs['artistid'] is not None:
            artistid = kwargs['artistid']
            artist = Artist.objects.get(pk=artistid)
            self.playlist.splice_artist(artist, player.playlistsong)
            player.shuffle = False 
            response = self._advance_play(player)
        elif 'playlistsongid' in kwargs and kwargs['playlistsongid'] is not None:
            self._advance_play(player, playlistsongid=kwargs['playlistsongid'])
            response = self._beatplayer_play(player)
        else:
            if player.state == Player.PLAYER_STATE_STOPPED:
                logger.debug("Player is stopped, but playing now")
                response = self._beatplayer_play(player)
            elif player.state == Player.PLAYER_STATE_PAUSED:
                logger.debug("Player is paused, but pause-toggling now")
                response = self._beatplayer_pause()
                if response and response['success']:
                    player.state = Player.PLAYER_STATE_PLAYING
        return response
    
    def next(self, player, **kwargs):
        response = None 
        self._advance(player)
        if player.state != Player.PLAYER_STATE_STOPPED:
            response = self._beatplayer_play(player)        
        return response
    
    def next_artist(self, player, **kwargs):        
        response = None 
        song = player.playlistsong.song
        current_artist = song.album.artist.id 
        while song.album.artist.id == current_artist:
            cursor_set = self._advance(player)
            song = player.playlistsong.song
        if player.state != Player.PLAYER_STATE_STOPPED:            
            response = self._beatplayer_play(player)
        return response 
    
    def toggle_shuffle(self, player, **kwargs):
        player.shuffle = not player.shuffle
        
    def toggle_repeat_song(self, player, **kwargs):
        player.repeat_song = not player.repeat_song 
        
    def volume_down(self, player, **kwargs):
        response = self._beatplayer_volume_down()
        #self.set_volume(volume=response['data']['volume'])
        return response
        
    def volume_up(self, player, **kwargs):
        response = self._beatplayer_volume_up()
        #self.set_volume(volume=response['data']['volume'])
        return response
    
    def remove(self, player, **kwargs):
        response = None 
        if 'playlistsongid' in kwargs and kwargs['playlistsongid'] is not None:
            response = self.playlist.remove_song(kwargs['playlistsongid'])
        elif 'albumid' in kwargs and kwargs['albumid'] is not None:
            response = self.playlist.remove_album(kwargs['albumid'])
        elif 'artistid' in kwargs and kwargs['artistid'] is not None:
            response = self.playlist.remove_artist(kwargs['artistid'])
        else:
            logger.debug("playlistsongid not found in kwargs: %s" % (kwargs))
        return response 
    
    def splice(self, player, **kwargs):
        song = None 
        album = None 
        artist = None 
        response = None
        if 'songid' in kwargs and kwargs['songid'] is not None:  
            songid = kwargs['songid']
            song = Song.objects.get(pk=songid)
            response = self.playlist.splice_song(song, player.playlistsong)
        elif 'albumid' in kwargs and kwargs['albumid'] is not None:
            albumid = kwargs['albumid']
            album = Album.objects.get(pk=albumid)
            response = self.playlist.splice_album(album, player.playlistsong)
        elif 'artistid' in kwargs and kwargs['artistid'] is not None:
            artistid = kwargs['artistid']
            artist = Artist.objects.get(pk=artistid)
            response = self.playlist.splice_artist(artist, player.playlistsong)
        return response
    
    def enqueue(self, player, **kwargs):
        playlist_id = kwargs['playlist_id'] if 'playlist_id' in kwargs else None 
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
    
    
        
