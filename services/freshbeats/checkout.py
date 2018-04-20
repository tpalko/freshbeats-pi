import sys
import os
import logging

#logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)

logger = logging.getLogger('FreshBeats')

sys.path.append(os.path.join(os.path.dirname(__file__), '../../webapp'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_env")

import config.settings
import django
from django.db.models import Q
django.setup()

from beater.models import Artist, Album, Song, AlbumCheckout, AlbumStatus

class AlbumManager:

	def __init__(self, *args, **kwargs):

		# - everything in Bytes
		self.free_bytes_margin = int(kwargs['free_bytes_margin'])
		self.device_free_bytes = int(kwargs['device_free_bytes'])
		
		# -- this is maintained for available space calculation
		self.checkout_delta = 0
		
		# -- these are maintained only for reporting
		self.albums_to_checkin = []
		self.albums_to_refresh = []
		self.albums_to_checkout = []

	def validate_plan(self):
		'''
		Reads the database, ensures the plan will work, and populates action lists. Proposed album check-outs are "made", if appropriate.
		'''

		db_albums_to_check_in = Album.objects.filter(action=Album.CHECKIN)
		logger.info("Registering %s previously marked albums to check-in.." % len(db_albums_to_check_in))
		self.checkin_albums(db_albums_to_check_in)

		db_requested_albums_to_check_out = Album.objects.filter(action=Album.REQUESTCHECKOUT, sticky=False)
		logger.info("Validating %s previously requested albums to check-out.." % len(db_requested_albums_to_check_out))
		for album in db_requested_albums_to_check_out:
			if not self.validate_checkout_album(album):
				logger.warn("Rejected checkout of %s/%s" % (album.artist.name, album.name))
				logger.warn("Would-be free space: %s B with %s B margin, leaving alone" %(self.real_available_bytes() - album.total_size, self.free_bytes_margin))	

		db_albums_to_check_out = Album.objects.filter(action=Album.CHECKOUT, sticky=False).order_by('request_priority')
		logger.info("Re-validating %s previously marked albums to check-out.." % len(db_albums_to_check_out))
		for album in db_albums_to_check_out:
			if not self.validate_checkout_album(album):
				logger.warn("Rejected checkout of %s/%s" % (album.artist.name, album.name))
				logger.warn("Would-be free space: %s B with %s B margin, leaving alone" %(self.real_available_bytes() - album.total_size, self.free_bytes_margin))	

		db_albums_to_refresh = Album.objects.filter(action=Album.REFRESH)
		logger.info("Validating %s previously marked albums to refresh.." % len(db_albums_to_refresh))
		for album in db_albums_to_refresh:
			if not self.validate_refresh_album(album):
				logger.warn("Rejected refresh of %s/%s" %(album.artist.name, album.name))
				delta = album.total_size - album.old_total_size
				logger.debug("Would-be free space: %s B with %s B margin, Action is %s" %(self.real_available_bytes() - delta, self.free_bytes_margin, Album.DONOTHING))	

		self.send_status_to_logger()

	def send_status_to_logger(self):

		logger.info("-- Device Status -- ")
		logger.info(" Device Free: {0:>10}".format(self.device_free_bytes))
		logger.info(" Free Margin: {0:>10}".format(self.free_bytes_margin))
		logger.info("-- Update Plan -- ")
		logger.info(" Checking-in: {0:>10}".format(sum([ a.total_size for a in self.albums_to_checkin ])))
		logger.info("  Refreshing: {0:>10}".format(sum([ a.total_size - a.old_total_size for a in self.albums_to_refresh ])))
		logger.info("Checking-out: {0:>10}".format(sum([ a.total_size for a in self.albums_to_checkout ])))
		logger.info(" Plan Result: {0:>10}".format(self.checkout_delta))

	def plan_available_bytes(self):		

		avail = self.device_free_bytes - self.free_bytes_margin - self.checkout_delta

		if avail > 0:
			return avail

		return 0

	def real_available_bytes(self):

		real_avail = self.device_free_bytes - self.checkout_delta

		return real_avail

	def checkin_albums(self, albums):

		for album in albums:
			
			album.action = Album.CHECKIN
			album.save()

			self.albums_to_checkin.append(album)
			self.checkout_delta -= album.total_size

	def validate_refresh_album(self, album):

		valid = False

		delta = album.total_size - album.old_total_size
	
		logger.debug("Delta is %s, available = %s" % (delta, self.plan_available_bytes()))

		if self.plan_available_bytes() < delta:		
			
			album.action = Album.DONOTHING
			album.save()
		else:
			self.albums_to_refresh.append(album)
			self.checkout_delta += delta
			valid = True

		return valid

	def validate_checkout_album(self, album):
		'''
		Formalizes an otherwise proposed album check-out.
		'''

		valid = False

		if self.plan_available_bytes() >= album.total_size:			
			self.albums_to_checkout.append(album)
			self.checkout_delta += album.total_size
			if album.action == Album.REQUESTCHECKOUT:
				album.action = Album.CHECKOUT
				album.save()
			valid = True
		else:
			pass
			#album.action = None
			#album.save()

		return valid

	def checkout_album(self, album):
		'''
		Checks-out an album cold.
		'''

		valid = False

		if self.validate_checkout_album(album):

			if album.action != Album.REQUESTCHECKOUT and not album.sticky:
				album.request_priority = 2

			album.action = Album.CHECKOUT
			album.save()

			valid = True
		else:
			pass

		return valid
			