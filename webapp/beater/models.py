from __future__ import unicode_literals
from django.db import models


# class Device(models.Manager):
#
#     name = models.CharField(max_length=255)
#     ip_address = models.IPAddress
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)


class AlbumManager(models.Manager):

    def get_queryset(self):
        return super(AlbumManager, self).get_queryset().filter(deleted=False)


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

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name


class AlbumCheckout(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    checkout_at = models.DateTimeField()
    return_at = models.DateTimeField(null=True)


class PlaylistSong(models.Model):
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    is_current = models.BooleanField(null=False, default=False)
    queue_number = models.IntegerField(null=False, default=1)
    play_count = models.IntegerField(null=False, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class Player(models.Model):
    PLAYER_STATE_STOPPED = 'stopped'
    PLAYER_STATE_PLAYING = 'playing'
    PLAYER_STATE_PAUSED = 'paused'

    PLAYLIST_MODE_ON = 'on'
    PLAYLIST_MODE_OFF = 'off'

    CURSOR_MODE_NEXT = 'next'
    CURSOR_MODE_STATIC = 'static'
    
    PLAYER_STATE_CHOICES = (
        (PLAYER_STATE_STOPPED, 'Stopped'),
        (PLAYER_STATE_PLAYING, 'Playing'),
        (PLAYER_STATE_PAUSED, 'Paused')
    )
    
    PLAYLIST_MODE_CHOICES = (
        (PLAYLIST_MODE_ON, 'On'),
        (PLAYLIST_MODE_OFF, 'Off')
    )
    
    CURSOR_MODE_CHOICES = (
        (CURSOR_MODE_NEXT, 'Next'),
        (CURSOR_MODE_STATIC, 'Static')
    )

    mute_state = models.BooleanField(null=False, default=False)
    shuffle_state = models.BooleanField(null=False, default=False)
    playlist_mode = models.CharField(max_length=3, choices=PLAYLIST_MODE_CHOICES, default=PLAYLIST_MODE_ON, null=False)
    state = models.CharField(max_length=7, choices=PLAYER_STATE_CHOICES, default=PLAYER_STATE_STOPPED, null=False)
    cursor_mode = models.CharField(max_length=6, choices=CURSOR_MODE_CHOICES, default=CURSOR_MODE_NEXT, null=False)
