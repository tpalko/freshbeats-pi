#from __future__ import unicode_literals
import logging 
# import time 
# import threading 
import json
# import requests 
# from urllib import parse 
from datetime import datetime
from dirtyfields import DirtyFieldsMixin
from django.db import models
# from django.shortcuts import reverse
# from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
# from .common.util import get_localized_now

logger = logging.getLogger()

# class PlayerPlaylistManager(models.Manager):
# 
#     def get_queryset(self):
#         return super(PlayerPlaylistManager, self).get_queryset()

## request session 
# playlist_id 
# device_id 
# switchboard_connection_id
# user_agent 
# mobile_id 

class CacheManager(models.Manager):
    
    # stale = False 
    
    def get_queryset(self):
        # logger.debug(self)
        return super(CacheManager, self).get_queryset()
    
    def create(self, **kwargs):
        # self.stale = True
        # logger.debug("creating") 
        return super(CacheManager, self).create(**kwargs)

class AlbumManager(CacheManager):

    def get_queryset(self):
        return super(AlbumManager, self).get_queryset().filter(deleted=False)
        
class Artist(models.Model):
    
    objects = CacheManager()
    
    name = models.CharField(max_length=255)
    musicbrainz_artistid = models.CharField(max_length=36, null=True)
    followed = models.BooleanField(default=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.name

class Album(models.Model):

    # -- state property values used to sort a planned action album into either 
    # -- remainder or checked-out bins when its action is cancelled 
    STATE_CHECKEDIN = 'checkedin'
    STATE_CHECKEDOUT = 'checkedout'

    # # -- on Album, 'action' means the album is in a transition state 
    # # -- after applying the "plan", action clears 
    # CHECKIN = 'checkin' # -- planned to check in 
    # REFRESH = 'refresh' # -- planned to update from source 
    # CHECKOUT = 'checkout' # -- planned to check out 
    # DONOTHING = 'donothing' # -- plan specifically to not check in (survey response of 'keep' or 'sticky')
    # REQUESTCHECKOUT = 'requestcheckout' # -- planned to validate for free space and become 'checkout'
    # 
    # ALBUM_ACTION_CHOICES = (
    #     (CHECKIN, 'Check-In'),
    #     (REFRESH, 'Refresh'),
    #     (CHECKOUT, 'Check-Out'),
    #     (DONOTHING, 'Do Nothing')
    # )
    '''
    Album.action + AlbumCheckout timestamps only 
    1. action = none 
    2. action = requestcheckout 
    3. action = checkout, albumcheckout.checkout_at = now 
    4. action = none, albumcheckout.checkout_at = now 
    5. action = refresh, albumcheckout.checkout_at = now 
    6. action = none, albumcheckout.checkout_at = now 
    7. action = checkin, albumcheckout.checkout_at = now 
    8. action = none, albumcheckout.checkout_at = now, return_at = now 
    
    AlbumCheckout.state + timestamps (no Album.action)
    1. albumcheckout <no record>
    2. albumcheckout.state = requested, next_state = None 
    3. albumcheckout.state = validated, next_state = checkedout  
    4. albumcheckout.state = checkedout, next_state = None,         checkedout_at = now 
    5. albumcheckout.state = checkedout, next_state = refresh,      checkedout_at = now 
    6. albumcheckout.state = checkedout, next_state = None,         checkedout_at = now 
    7. albumcheckout.state = checkedout, next_state = checkedin,    checkedout_at = now 
    8. albumcheckout.state = checkedin,  next_state = None,         checkedout_at = now, return_at = now 
    '''

    LOVEIT = 'loveit'
    MIXITUP = 'mixitup'
    NOTHANKS = 'nothanks'
    NOTGOOD = 'notgood'
    UNDECIDED = 'undecided'
    UNRATED = 'unrated'

    ALBUM_RATING_CHOICES = (
        (LOVEIT, 'Love it'),
        (MIXITUP, 'Not my thing, but nice to mix it up'),
        (NOTHANKS, 'Good, but OK if I never hear it again'),
        (NOTGOOD, 'Not good'),
        (UNDECIDED, 'Undecided'),
        (UNRATED, 'Unrated')
    )

    # objects = AlbumManager()

    artist = models.ForeignKey(Artist, null=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    tracks = models.IntegerField(default=0)
    date = models.CharField(max_length=50, null=True)
    musicbrainz_albumid = models.CharField(max_length=36, null=True)    
    musicbrainz_trmid = models.CharField(max_length=36, null=True)
    genre = models.CharField(max_length=50, null=True)
    organization = models.CharField(max_length=100, null=True)
    audio_size = models.BigIntegerField(default=0)
    total_size = models.BigIntegerField(default=0)
    old_total_size = models.BigIntegerField(null=True)
    rating = models.CharField(max_length=20, choices=ALBUM_RATING_CHOICES, null=False, default=UNRATED)
    sticky = models.BooleanField(null=False, default=False)
    # rip = models.BooleanField(null=False, default=False)
    # owned = models.BooleanField(null=False, default=False)
    # wanted = models.BooleanField(null=False, default=False)
    # action = models.CharField(max_length=20, choices=ALBUM_ACTION_CHOICES, null=True)
    # request_priority = models.IntegerField(null=False, default=1)
    deleted = models.BooleanField(null=False, default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def total_size_in_mb(self):
        '''total_size (bytes) reported in MB'''
        return 1.0*(self.total_size)/(1024*1024)

    def current_albumcheckout(self, mobile_id):
        '''Returns first outstanding (return_at=None) checkout'''
        checkouts = self.albumcheckout_set.filter(mobile_id=mobile_id, return_at=None)
        if len(checkouts) > 0:
            return checkouts[0]
        return None

    def is_refreshable(self, mobile_id):
        '''Has been updated since current checkout?'''
        albumcheckout = self.current_albumcheckout(mobile_id)
        if self.updated_at > albumcheckout.checkout_at:
            return True
        else:
            return False

    def replace_statuses(self, new_statuses):
        '''Removes all statuses and adds given ones'''
        for s in self.albumstatus_set.all():
            s.delete()

        for s in new_statuses:
            a = AlbumStatus(album=self, status=s)
            a.save()

    def has_status(self, status):
        '''Does album have given status?'''
        return status in [ s.status for s in self.albumstatus_set.all() ]

    def remove_status(self, status):
        '''Assumes given status exists and removes it'''
        albumstatus = self.albumstatus_set.filter(status=status)
        albumstatus.delete()
    
    # def play_recency_score(self):dd
    #     total_count = sum([ s.play_count or 0])

    def __unicode__(self):
        return self.name

class AlbumStatus(models.Model):

    INCOMPLETE = 'incomplete'
    MISLABELED = 'mislabeled'
    RIPPINGPROBLEM = 'rip'
    OWNED = 'owned'
    WANTED = 'wanted'
    FOLLOW = 'follow'

    ALBUM_STATUS_CHOICES = (
        (INCOMPLETE, 'The album is incomplete'),
        (MISLABELED, 'The album is mislabeled'),
        (RIPPINGPROBLEM, 'The album has ripping problems'),
        (OWNED, 'The album exists materially'),
        (WANTED, 'This album is sought after'),
        (FOLLOW, 'The artist is of particular interest')
    )
    
    objects = CacheManager()
    
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=ALBUM_STATUS_CHOICES, null=False)

class Song(models.Model):
    
    objects = CacheManager()
    
    album = models.ForeignKey(Album, on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    sha1sum = models.CharField(max_length=40, null=True)
    tracknumber = models.IntegerField(null=True)
    title = models.CharField(max_length=255, null=True)
    musicbrainz_trackid = models.CharField(max_length=36, null=True)
    url = models.URLField(max_length=2048, null=True)
    play_count = models.IntegerField(null=False, default=0)
    last_played_at = models.DateTimeField(null=True)
    
    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name
    
    def tags(self, music_path):
        e = easyid3.EasyID3(os.path.join(music_path, self.artist.name, self.album.name, self.name))
        return e.keys()
    
    def set_tag(self, music_path, key, value):
        e = easyid3.EasyID3(os.path.join(music_path, self.artist.name, self.album.name, self.name))
        e[key] = value 
        e.save()
        
    def get_tag(self, music_path, key):
        e = easyid3.EasyID3(os.path.join(music_path, self.artist.name, self.album.name, self.name))
        if key in e.keys():
            return e[key]
        return None 

class Mobile(DirtyFieldsMixin, models.Model):
    
    objects = CacheManager()
    
    name = models.CharField(null=False, max_length=50)
    ip_address = models.GenericIPAddressField(protocol='IPv4', null=True, blank=True)
    ssh_username = models.CharField(null=True, max_length=50, blank=True)
    ssh_private_key_path = models.CharField(null=True, max_length=255, blank=True)
    target_path = models.CharField(null=False, max_length=255)
    
    def state_bins(self):
        
        mobile_checkouts = self.albumcheckout_set.all()
        valid_states = [AlbumCheckout.REQUESTED, AlbumCheckout.VALIDATED, AlbumCheckout.CHECKEDOUT, AlbumCheckout.REFRESH, AlbumCheckout.CHECKEDIN]
        state_bins = { state: [ac for ac in mobile_checkouts if ac.state == state] for state in valid_states }
        
        return state_bins 
        
        # checked_out_album_next_state_bins = {state: [ac.album for ac in mobile_checkouts if ac.next_state == state] for state in [AlbumCheckout.REFRESH, AlbumCheckout.CHECKEDIN]}
        # # -- bin by state: sum total_size if checkin, otherwise size delta 
        # checked_out_album_next_state_sizes = {state: sum([ac.album.total_size if ac.next_state == AlbumCheckout.CHECKEDIN else (ac.album.total_size - ac.album.old_total_size) for ac in mobile_checkouts if ac.state == state])/(1024*1024) for state in [AlbumCheckout.REFRESH, AlbumCheckout.CHECKEDIN]}
        # checked_out_no_state_albums = [ ac.album for ac in mobile_checkouts if ac.next_state is None ]
        # for album in checked_out_no_state_albums:
        #     album.mobile_state = album.current_albumcheckout(mobile.id)
        # checked_out_no_state_albums_size = sum([ album.total_size for album in checked_out_no_state_albums ])/(1024*1024)
        # 
        # mobile_state = mobile.albumcheckout_set.filter(Q(state=AlbumCheckout.REQUESTED) | Q(state=AlbumCheckout.VALIDATED))
        # mobile_state_bins = { state: [ac.album for ac in mobile_state if ac.state == state] for state in [AlbumCheckout.REQUESTED, AlbumCheckout.VALIDATED] }
        # mobile_state_bin_sizes = { state: sum([ac.total_size for ac in mobile_state_bins[state]])/(1024*1024) for state in mobile_state_bins }
    
class AlbumCheckout(models.Model):
    
    REQUESTED = 'requested'
    VALIDATED = 'validated'
    CHECKEDOUT = 'checkedout'
    REFRESH = 'refresh'
    CHECKEDIN = 'checkedin'
    
    ALBUMCHECKOUT_STATE_CHOICES = (
        (REQUESTED, 'Requested'),
        (VALIDATED, 'Validated'),
        (CHECKEDOUT, 'Checked-out'),
        (CHECKEDIN, 'Checked-in')
    )
    
    ALBUMCHECKOUT_NEXT_STATE_CHOICES = (
        (CHECKEDOUT, 'Checked-out'),
        (REFRESH, 'Refresh'),
        (CHECKEDIN, 'Checked-in')
    )
    
    objects = CacheManager()
    
    album = models.ForeignKey(Album, on_delete=models.PROTECT)
    mobile = models.ForeignKey(Mobile, on_delete=models.CASCADE, null=True)
    checkout_at = models.DateTimeField(null=True)
    return_at = models.DateTimeField(null=True)
    state = models.CharField(max_length=20, choices=ALBUMCHECKOUT_STATE_CHOICES, default=REQUESTED)
    next_state = models.CharField(max_length=20, null=True, choices=ALBUMCHECKOUT_NEXT_STATE_CHOICES)
    request_priority = models.IntegerField(null=False, default=1)
    
    '''
     2. albumcheckout.state = requested, next_state = None 
     3. albumcheckout.state = validated, next_state = checkedout  
     4. albumcheckout.state = checkedout, next_state = None,         checkedout_at = now 
     5. albumcheckout.state = checkedout, next_state = refresh,      checkedout_at = now 
     6. albumcheckout.state = checkedout, next_state = None,         checkedout_at = now 
     7. albumcheckout.state = checkedout, next_state = checkedin,    checkedout_at = now 
     8. albumcheckout.state = checkedin,  next_state = None,         checkedout_at = now, return_at = now 
     '''
    def clean(self):        
        if self.state in [AlbumCheckout.REQUESTED, AlbumCheckout.CHECKEDIN]:
            if self.next_state is not None:
                raise ValidationError({'next_state': _('Next state cannot be set when state is requested or checked-in')})
        elif self.state in [AlbumCheckout.VALIDATED]:
            if self.next_state != AlbumCheckout.CHECKEDOUT:
                raise ValidationError({'next_state': _('Next state must be checked-out when state is validated')})
        elif self.state in [AlbumCheckout.CHECKEDOUT]:
            if self.next_state not in [None, AlbumCheckout.REFRESH, AlbumCheckout.CHECKEDIN]:
                raise ValidationError({'next_state': _('Next state must be refresh, checked-in, or not set when state is checked-out')})
                
    def save(self, *args, **kwargs):
        self.clean()
        super(AlbumCheckout, self).save(*args, **kwargs)
    
class Playlist(models.Model):
    
    objects = CacheManager()
    
    name = models.CharField(max_length=50, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class PlaylistSong(models.Model):
    
    objects = CacheManager()
    
    song = models.ForeignKey(Song, on_delete=models.PROTECT)
    queue_number = models.IntegerField(null=False, default=1)
    play_count = models.IntegerField(null=False, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    last_played_at = models.DateTimeField(null=True)
    playlist = models.ForeignKey(Playlist, null=True, on_delete=models.CASCADE)

class Player(DirtyFieldsMixin, models.Model):
    '''The state of a media-playing process behind a services.beatplayer API'''

    PLAYER_STATE_STOPPED = 'stopped'
    PLAYER_STATE_PLAYING = 'playing'
    PLAYER_STATE_PAUSED = 'paused'

    # -- typically, to 'next' during 'playing' state, we simply call 'stop' 
    # -- and rely on the callback to advance the cursor 
    # -- but if we need to cue a position prior to calling 'stop'
    # -- because it's not a simple 'next'
    # -- we tell it to not advance on the callback 
    # -- alternatively, we could pass some flag to 'stop'
    # -- which would be returned in the callback 
    # -- but I prefer to leave the player out of it
    CURSOR_MODE_NEXT = 'next'
    CURSOR_MODE_STATIC = 'static'
    PLAYER_STATE_CHOICES = (
        (PLAYER_STATE_STOPPED, 'Stopped'),
        (PLAYER_STATE_PLAYING, 'Playing'),
        (PLAYER_STATE_PAUSED, 'Paused')
    )
    
    CURSOR_MODE_CHOICES = (
        (CURSOR_MODE_NEXT, 'Next'),
        (CURSOR_MODE_STATIC, 'Static')
    )
    
    # playlist = PlayerPlaylistManager()
    objects = CacheManager()
    
    parent = models.ForeignKey('Player', null=True, on_delete=models.PROTECT)
    preceding_command = models.CharField(max_length=255, null=True)
    preceding_command_args = models.CharField(max_length=1024, null=True)
    mute = models.BooleanField(null=False, default=False)
    shuffle = models.BooleanField(null=False, default=False)
    time_remaining = models.DecimalField(max_digits=4, decimal_places=0, default=0)
    time_pos = models.DecimalField(max_digits=4, decimal_places=0, default=0)
    percent_pos = models.DecimalField(max_digits=4, decimal_places=0, default=0)
    state = models.CharField(max_length=7, choices=PLAYER_STATE_CHOICES, default=PLAYER_STATE_STOPPED, null=False)
    cursor_mode = models.CharField(max_length=6, choices=CURSOR_MODE_CHOICES, default=CURSOR_MODE_NEXT, null=False)
    repeat_song = models.BooleanField(null=False, default=False)
    beatplayer_status = models.CharField(max_length=20, null=True)
    beatplayer_registered_at = models.DateTimeField(null=True)
    volume = models.IntegerField(null=True)
    playlistsong = models.ForeignKey(PlaylistSong, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
    
        original_song = self._original_state['playlistsong'] # -- playlistsong ID 
        current_song = self.playlistsong.id if self.playlistsong else None
        song_changed = current_song != original_song
        not_time_related_dirty_fields = [ f for f in self.get_dirty_fields() if f not in ['time_pos', 'percent_pos', 'time_remaining'] ]
        save_triggering_fields = [ a for a in self.__dict__ if a not in ['created_at', 'parent_id', 'updated_at', 'preceding_command', 'preceding_command_args', 'id', '_state', '_original_state'] ]
        insert_triggering_dirty_fields = [ s for s in save_triggering_fields if s in not_time_related_dirty_fields ]
        other_dirty_fields = len(insert_triggering_dirty_fields) > 0
        '''
        >>> p._original_state.keys()
        dict_keys(['created_at', 'beatplayer_status', 'beatplayer_registered_at', 'time_pos', 'parent', 'percent_pos', 'cursor_mode', 'mute', 'playlistsong', 'shuffle', 'preceding_command', 'volume', 'state', 'time_remaining', 'preceding_command_args', 'id', 'repeat_song', 'updated_at'])
        >>> p.__dict__.keys()
        dict_keys(['created_at', 'beatplayer_status', 'beatplayer_registered_at', 'time_pos', 'parent_id', 'percent_pos', 'cursor_mode', 'mute', 'playlistsong_id', 'shuffle', 'preceding_command', 'volume', 'state', 'time_remaining', 'preceding_command_args', 'id', 'repeat_song', 'updated_at', '_state', '_original_state'])
        '''

        if song_changed or other_dirty_fields:
            # logger.debug("Inserting a new player (new song? %s, other dirty fields? %s)" % (song_changed, ",".join(insert_triggering_dirty_fields)))
            self.parent_id = self.id 
            self.id = None         
    
        super(Player, self).save(*args, **kwargs)
    
        # -- if we inserted, this will go around back and make the connection 
        # -- when self becomes a new record, self.device ostensibly comes along for the ride
        # -- however the update for self.device.player is not seen in the database 
        # -- there is probably some django model attribute that would fix this behavior
        if song_changed or other_dirty_fields:
            logger.debug("Moving device %s from player %s -> %s" % (self.device.id, self.parent_id, self.id))
            self.device.player = self 
            self.device.save()
        
    def status_dump(self):
        return json.dumps({
            'mute': self.mute, 
            'shuffle': self.shuffle,
            'volume': self.volume,
            'playlistsong': self.playlistsong.song.name if self.playlistsong else None,
            'state': self.state,
            'time_remaining': float(self.time_remaining),
            'cursor_mode': self.cursor_mode,
            'repeat_song': self.repeat_song,
            'beatplayer_status': self.beatplayer_status,
            'beatplayer_registered_at': datetime.strftime(self.beatplayer_registered_at, "%c") if self.beatplayer_registered_at else None 
        }, indent=4)
        
    # def compare(self, p1):
    #     # -- may need to hit this due to lazy load and __dict__ access 
    #     ps = p1.playlistsong
    #     for a in [ a for a in self.__dict__ if a not in ['created_at', 'updated_at', 'preceding_command', 'preceding_command_args', 'id', '_state', '_device_cache'] ]:
    #         ao = self.__dict__[a]
    #         bo = None 
    #         if a in p1.__dict__:
    #             bo = p1.__dict__[a]
    #         if ao != bo:
    #             logger.debug("Comparing player states found a difference in property '%s': instance value '%s' != db value '%s'" % (a, ao, bo))
    #             return False 
    #     #logger.debug("%s == %s" % (self.__dict__, p1.__dict__))                
    #     return True 
    
    # def save(self, *args, **kwargs):
    #     self.parent_id = self.id 
    #     self.id = None 
    #     self.created_at = None 
    #     self.updated_at = None 
    #     super(Player, self).save(*args, **kwargs)

class DeviceHealth(DirtyFieldsMixin, models.Model):
    '''Readiness and liveness of a services.beatplayer API'''

    DEVICE_STATUS_UNKNOWN = 'unknown'
    DEVICE_STATUS_READY = 'ready'
    DEVICE_STATUS_NOTREADY = 'notready'
    DEVICE_STATUS_DOWN = 'down'
    
    DEVICE_STATUS_CHOICES = (
        (DEVICE_STATUS_UNKNOWN, 'Unknown'),
        (DEVICE_STATUS_READY, 'Ready'),
        (DEVICE_STATUS_NOTREADY, 'Not Ready'),
        (DEVICE_STATUS_DOWN, 'Down')
    )
    
    objects = CacheManager()
    
    last_client_presence = models.DateTimeField(null=True)
    registered_at = models.DateTimeField(null=True)
    last_device_health_report = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, choices=DEVICE_STATUS_CHOICES, default=DEVICE_STATUS_DOWN, null=False)
    reachable = models.BooleanField(null=False, default=False)
    mounted = models.BooleanField(null=False, default=False)
   
class Device(DirtyFieldsMixin, models.Model):
    '''An abstraction of a services.beatplayer API, referencing its state and health'''

    DEVICE_STATUS_READY = 'ready'
    DEVICE_STATUS_NOTREADY = 'notready'
    DEVICE_STATUS_DOWN = 'down'
    
    DEVICE_STATUS_CHOICES = (
        (DEVICE_STATUS_READY, 'Ready'),
        (DEVICE_STATUS_NOTREADY, 'Not Ready'),
        (DEVICE_STATUS_DOWN, 'Down')
    )
    
    objects = CacheManager()
    
    player = models.OneToOneField(Player, null=True, on_delete=models.CASCADE)
    health = models.OneToOneField(DeviceHealth, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(protocol='IPv4')
    agent_base_url = models.CharField(max_length=255)    
    is_active = models.BooleanField(null=False, default=True)    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
        
    def save(self, *args, **kwargs):       
        is_new = self.id is None
        activating = self.is_active and 'is_active' in self.get_dirty_fields()

        if is_new or not self.health:
            logger.info("Filling in missing DeviceHealth for device %s" % self.id)
            self.health = DeviceHealth.objects.create(
                status = DeviceHealth.DEVICE_STATUS_NOTREADY,
                reachable = False,
                mounted = False
            )
            
        super(Device, self).save(*args, **kwargs)

    def _human_date(self, val):
        # return datetime.strftime(val, "%Y-%m-%d %H:%M:%S") if val else None
        return datetime.strftime(val, "%c") if val else None

    def status_dump(self):
        return json.dumps({
            'id': self.id,
            'agent_base_url': self.agent_base_url,
            'registered_at': self._human_date(self.health.registered_at),
            'last_device_health_report': self._human_date(self.health.last_device_health_report),
            'status': self.health.status,
            'reachable': self.health.reachable,
            'mounted': self.health.mounted
        }, indent=4)
    
# class PlayerTemp(models.Model):
# 
#     updated_at = models.DateTimeField(auto_now=True)
#     created_at = models.DateTimeField(default=get_localized_now)

class Log(models.Model):

    objects = CacheManager()
    
    levelname = models.CharField(null=True, max_length=255) 
    levelno = models.IntegerField(null=False, default=1)
    message = models.TextField(null=True) 
    asctime = models.DateTimeField()
    processName = models.CharField(null=True, max_length=255) 
    funcName = models.CharField(null=True, max_length=255) 
    name = models.CharField(null=True, max_length=255) 
    lineno = models.IntegerField(null=False, default=1)
    pathname = models.CharField(null=True, max_length=255) 
    
