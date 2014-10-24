from django.db import models

# Create your models here.

class Album(models.Model):

	REMOVE='remove'
	UPDATE='update'
	ADD='add'
	DONOTHING='donothing'

	ALBUM_ACTION_CHOICES = (
		(REMOVE, 'Remove'),
		(UPDATE, 'Update'),
		(ADD, 'Add'),
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
	
	artist = models.CharField(max_length=255)
	name = models.CharField(max_length=255)
	tracks = models.IntegerField()
	size = models.BigIntegerField()
	old_size = models.BigIntegerField()
	rating = models.CharField(max_length=20, choices=ALBUM_RATING_CHOICES, null=False, default=UNRATED)
	action = models.CharField(max_length=20, choices=ALBUM_ACTION_CHOICES, null=True)	
	created_at = models.DateTimeField(auto_now_add = True)
	updated_at = models.DateTimeField(auto_now = True)

	def current_albumcheckout(self):
		checkouts = self.albumcheckout_set.filter(return_at=None)
		if len(checkouts) > 0:
			return checkouts[0]

	def is_updatable(self):		
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

class AlbumCheckout(models.Model):
	album = models.ForeignKey(Album)
	checkout_at = models.DateTimeField()
	return_at = models.DateTimeField(null=True)
	