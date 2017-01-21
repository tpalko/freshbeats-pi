import sys
import os
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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

		db_albums_to_check_in = Album.objects.filter(action=Album.CHECKIN)
		logger.info("Registering %s previously marked albums to check-in.." % len(db_albums_to_check_in))
		self.checkin_albums(db_albums_to_check_in)

		db_requested_albums_to_check_out = Album.objects.filter(action=Album.REQUESTCHECKOUT, sticky=False)
		#logger.info("Registering %s previously requested albums to check-out.." % len(db_requested_albums_to_check_out))
		for album in db_requested_albums_to_check_out:
			if not self.validate_checkout_album(album):
				logger.warn("Rejected checkout of %s/%s" % (album.artist.name, album.name))

		db_albums_to_check_out = Album.objects.filter(action=Album.CHECKOUT, sticky=False).order_by('request_priority')
		#logger.info("Registering %s previously marked albums to check-out.." % len(db_albums_to_check_out))
		for album in db_albums_to_check_out:
			if not self.validate_checkout_album(album):
				logger.warn("Rejected checkout of %s/%s" % (album.artist.name, album.name))

		db_albums_to_refresh = Album.objects.filter(action=Album.REFRESH)
		#logger.info("Registering %s previously marked albums to refresh.." % len(db_albums_to_refresh))
		for album in db_albums_to_refresh:
			if not self.validate_refresh_album(album):
				logger.warn("Rejected refresh of %s/%s" %(album.artist.name, album.name))

		self.send_status_to_logger()

	def send_status_to_logger(self):

		logger.info("-- Device Status -- ")
		logger.info(" Device Free: {0:>10}".format(self.device_free_bytes))
		logger.info(" Free Margin: {0:>10}".format(self.free_bytes_margin))
		logger.info("   Available: {0:>10}".format(self.device_free_bytes - self.free_bytes_margin))
		logger.info("-- Update Plan -- ")
		logger.info(" Checking-in: {0:>10}".format(sum([ a.total_size for a in self.albums_to_checkin ])))
		logger.info("  Refreshing: {0:>10}".format(sum([ a.total_size - a.old_total_size for a in self.albums_to_refresh ])))
		logger.info("Checking-out: {0:>10}".format(sum([ a.total_size for a in self.albums_to_checkout ])))
		logger.info(" Plan Result: {0:>10}".format(self.available_bytes()))

	def available_bytes(self):		

		avail = self.device_free_bytes - self.free_bytes_margin - self.checkout_delta

		if avail > 0:
			return avail

		return 0

	def checkin_albums(self, albums):

		for album in albums:
			
			album.action = Album.CHECKIN
			album.save()

			self.albums_to_checkin.append(album)
			self.checkout_delta -= album.total_size

	def validate_refresh_album(self, album):

		valid = False

		delta = album.total_size - album.old_total_size
	
		logger.debug("Delta is %s, available = %s" % (delta, self.available_bytes()))

		if self.available_bytes() < delta:		
			logger.debug("Would-be free space: %s, Action is %s" %(self.available_bytes() - delta, Album.DONOTHING))	
			album.action = Album.DONOTHING
			album.save()
		else:
			self.albums_to_refresh.append(album)
			self.checkout_delta += delta
			valid = True

		return valid

	def validate_checkout_album(self, album):

		valid = False

		if self.available_bytes() < album.total_size:
			logger.warn("Would-be free space: %s, leaving alone" %(self.available_bytes() - album.total_size))	
			#album.action = None
			#album.save()
		else:
			self.albums_to_checkout.append(album)
			self.checkout_delta += album.total_size
			if album.action == Album.REQUESTCHECKOUT:
				album.action = Album.CHECKOUT
				album.save()
			valid = True

		return valid

	def checkout_album(self, album):

		if self.validate_checkout_album(album):

			if album.action != Album.REQUESTCHECKOUT and not album.sticky:
				album.request_priority = 2

			album.action = Album.CHECKOUT
			album.save()
			