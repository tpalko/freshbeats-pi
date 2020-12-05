from __future__ import unicode_literals
from django.db import models
import logging 
import json
from datetime import datetime
from .common.util import get_localized_now

logger = logging.getLogger(__name__)

class CacheManager(models.Manager):
    
    stale = False 
    
    def get_queryset(self):
        logger.debug(self)
        return super(CacheManager, self).get_queryset()
    
    def create(self, **kwargs):
        self.stale = True
        logger.debug("creating") 
        super(CacheManager, self).create(**kwargs)

class AlbumManager(models.Manager):

    def get_queryset(self):
        return super(AlbumManager, self).get_queryset().filter(deleted=False)

class Device(models.Model):
    
    DEVICE_STATUS_READY = 'ready'
    DEVICE_STATUS_NOTREADY = 'notready'
    DEVICE_STATUS_DOWN = 'down'
    
    DEVICE_STATUS_CHOICES = (
        (DEVICE_STATUS_READY, 'Ready'),
        (DEVICE_STATUS_NOTREADY, 'Not Ready'),
        (DEVICE_STATUS_DOWN, 'Down')
    )
    
    name = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(protocol='IPv4')
    agent_base_url = models.CharField(max_length=255)
    registered_at = models.DateTimeField(null=True)
    last_health_check = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, choices=DEVICE_STATUS_CHOICES, default=DEVICE_STATUS_DOWN, null=False)
    reachable = models.BooleanField(null=False, default=False)
    registered = models.BooleanField(null=False, default=False)
    mounted = models.BooleanField(null=False, default=False)
    selfreport = models.BooleanField(null=False, default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def status_dump(self):
        return json.dumps({
            'id': self.id,
            'last_health_check': datetime.strftime(self.last_health_check, "%Y-%m-%d %H:%M:%S") if self.last_health_check else None, 
            'status': self.status, 
            'reachable': self.reachable,
            'registered': self.registered,
            'selfreport': self.selfreport,
            'mounted': self.mounted
        }, indent=4)
        
class Artist(models.Model):

    name = models.CharField(max_length=255)
    musicbrainz_artistid = models.CharField(max_length=36, null=True)
    followed = models.BooleanField(default=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.name

class Album(models.Model):

    STATE_CHECKEDIN = 'checkedin'
    STATE_CHECKEDOUT = 'checkedout'

    CHECKIN = 'checkin'
    REFRESH = 'refresh'
    CHECKOUT = 'checkout'
    DONOTHING = 'donothing'
    REQUESTCHECKOUT = 'requestcheckout'

    ALBUM_ACTION_CHOICES = (
        (CHECKIN, 'Check-In'),
        (REFRESH, 'Refresh'),
        (CHECKOUT, 'Check-Out'),
        (DONOTHING, 'Do Nothing')
    )

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

    objects = AlbumManager()

    artist = models.ForeignKey(Artist, null=True, on_delete=models.CASCADE)
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
    rip = models.BooleanField(null=False, default=False)
    owned = models.BooleanField(null=False, default=False)
    wanted = models.BooleanField(null=False, default=False)
    action = models.CharField(max_length=20, choices=ALBUM_ACTION_CHOICES, null=True)
    request_priority = models.IntegerField(null=False, default=1)
    deleted = models.BooleanField(null=False, default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def total_size_in_mb(self):
        '''total_size (bytes) reported in MB'''
        return 1.0*(self.total_size)/(1024*1024)

    def current_albumcheckout(self):
        '''Returns first outstanding (return_at=None) checkout'''
        checkouts = self.albumcheckout_set.filter(return_at=None)
        if len(checkouts) > 0:
            return checkouts[0]
        return None

    def is_refreshable(self):
        '''Has been updated since current checkout?'''
        albumcheckout = self.current_albumcheckout()
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
        statuses = map(lambda s: s.status, self.albumstatus_set.all())
        return status in statuses

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

    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=ALBUM_STATUS_CHOICES, null=False)

class Song(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    sha1sum = models.CharField(max_length=40, null=True)
    tracknumber = models.IntegerField(null=True)
    title = models.CharField(max_length=255, null=True)
    musicbrainz_trackid = models.CharField(max_length=36, null=True)
    play_count = models.IntegerField(null=False, default=0)
    last_played_at = models.DateTimeField(null=True)
    
    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name

class AlbumCheckout(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    checkout_at = models.DateTimeField()
    return_at = models.DateTimeField(null=True)

class Playlist(models.Model):
    name = models.CharField(max_length=50, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class PlaylistSong(models.Model):
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    is_current = models.BooleanField(null=False, default=False)
    queue_number = models.IntegerField(null=False, default=1)
    play_count = models.IntegerField(null=False, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    last_played_at = models.DateTimeField(null=True)
    playlist = models.ForeignKey(Playlist, null=True, on_delete=models.CASCADE)
    #objects = CacheManager()

class Player(models.Model):
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
    
    device = models.ForeignKey(Device, null=True, on_delete=models.CASCADE)
    preceding_command = models.CharField(max_length=255, null=True)
    preceding_command_args = models.CharField(max_length=255, null=True)
    mute = models.BooleanField(null=False, default=False)
    shuffle = models.BooleanField(null=False, default=False)
    time_remaining = models.DecimalField(max_digits=4, decimal_places=0, default=0)
    time_pos = models.DecimalField(max_digits=4, decimal_places=0, default=0)
    percent_pos = models.DecimalField(max_digits=4, decimal_places=0, default=0)
    state = models.CharField(max_length=7, choices=PLAYER_STATE_CHOICES, default=PLAYER_STATE_STOPPED, null=False)
    cursor_mode = models.CharField(max_length=6, choices=CURSOR_MODE_CHOICES, default=CURSOR_MODE_NEXT, null=False)
    repeat_song = models.BooleanField(null=False, default=False)
    beatplayer_status = models.CharField(max_length=20, null=True)
    beatplayer_registered = models.NullBooleanField()
    volume = models.IntegerField(null=True)
    playlistsong = models.ForeignKey(PlaylistSong, null=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=get_localized_now)
    updated_at = models.DateTimeField(auto_now=True)
    
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
            'beatplayer_registered': self.beatplayer_registered
        }, indent=4)
        
    def compare(self, p1):
        ps = p1.playlistsong
        for a in [ a for a in self.__dict__ if a not in ['created_at', 'updated_at', 'preceding_command', 'preceding_command_args', 'id', '_state'] ]:
            ao = self.__dict__[a]
            bo = None 
            if a in p1.__dict__:
                bo = p1.__dict__[a]
            if ao != bo:
                logger.debug("Comparing player states (%s): current %s != db %s" % (a, ao, bo))
                return False 
        #logger.debug("%s == %s" % (self.__dict__, p1.__dict__))                
        return True 
