from __future__ import unicode_literals

from django.db import models

class Artist(models.Model):

	name = models.CharField(max_length=255)
	created_at = models.DateTimeField(auto_now_add = True)
	updated_at = models.DateTimeField(auto_now = True)

class Album(models.Model):

	STATE_CHECKEDIN='checkedin'
	STATE_CHECKEDOUT='checkedout'

	CHECKIN='checkin'
	REFRESH='refresh'
	CHECKOUT='checkout'
	DONOTHING='donothing'
	REQUESTCHECKOUT='requestcheckout'

	ALBUM_ACTION_CHOICES = (
		(CHECKIN, 'Check-In'),
		(REFRESH, 'Refresh'),
		(CHECKOUT, 'Check-Out'),
		(DONOTHING, 'Do Nothing')
	)

	LOVEIT='loveit'
	MIXITUP='mixitup'
	NOTHANKS='nothanks'
	NOTGOOD='notgood'
	UNDECIDED='undecided'
	UNRATED='unrated'
	
	ALBUM_RATING_CHOICES = (
		(LOVEIT, 'Love it'),
		(MIXITUP, 'Not my thing, but nice to mix it up'),
		(NOTHANKS, 'Good, but OK if I never hear it again'),
		(NOTGOOD, 'Not good'),
		(UNDECIDED, 'Undecided'),
		(UNRATED, 'Unrated')
	)
	
	artist = models.ForeignKey(Artist, null=True)
	name = models.CharField(max_length=255)
	tracks = models.IntegerField()
	audio_size = models.BigIntegerField(default=0)
	total_size = models.BigIntegerField(default=0)
	old_total_size = models.BigIntegerField(null=True)
	rating = models.CharField(max_length=20, choices=ALBUM_RATING_CHOICES, null=False, default=UNRATED)
	sticky = models.BooleanField(null=False, default=False)
	action = models.CharField(max_length=20, choices=ALBUM_ACTION_CHOICES, null=True)	
	request_priority = models.IntegerField(null=False, default=1)
	created_at = models.DateTimeField(auto_now_add = True)
	updated_at = models.DateTimeField(auto_now = True)

	def total_size_in_mb(self):
		return 1.0*(self.total_size)/(1024*1024)

	def current_albumcheckout(self):
		checkouts = self.albumcheckout_set.filter(return_at=None)
		if len(checkouts) > 0:
			return checkouts[0]
		return None

	def is_refreshable(self):		
		albumcheckout = self.current_albumcheckout()
		if self.updated_at > albumcheckout.checkout_at:
			return True
		else:
			return False

	def replace_statuses(self, new_statuses):
		
		for s in self.albumstatus_set.all():
			s.delete()

		for s in new_statuses:
			a = AlbumStatus(album=self, status=s)
			a.save()

	def has_status(self, status):

		statuses = map(lambda s: s.status, self.albumstatus_set.all())
		return status in statuses

	def remove_status(self, status):

		albumstatus = self.albumstatus_set.filter(status=status)
		albumstatus.delete()

class AlbumStatus(models.Model):

	INCOMPLETE='incomplete'
	MISLABELED='mislabeled'
	RIPPINGPROBLEM='ripping problem'

	ALBUM_STATUS_CHOICES = (
		(INCOMPLETE, 'The album is incomplete'),
		(MISLABELED, 'The album is mislabeled'),
		(RIPPINGPROBLEM, 'The album has ripping problems')
	)

	album = models.ForeignKey(Album)
	status = models.CharField(max_length=20, choices=ALBUM_STATUS_CHOICES, null=False)

class Song(models.Model):
	album = models.ForeignKey(Album)
	name = models.CharField(max_length=255)
	sha1sum = models.CharField(max_length=40, null=True)

	class Meta:
		ordering = ('name',)

class AlbumCheckout(models.Model):
	album = models.ForeignKey(Album)
	checkout_at = models.DateTimeField()
	return_at = models.DateTimeField(null=True)
	
class PlaylistSong(models.Model):
	song = models.ForeignKey(Song)
	is_current = models.BooleanField(null=False, default=False)
	played = models.BooleanField(null=False, default=False)
	created_at = models.DateTimeField(auto_now_add=True)

