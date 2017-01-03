import sys
import os
import logging

logger = logging.getLogger(__name__)

sys.path.append(os.path.join(os.path.dirname(__file__), '../../webapp'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import config.settings
from beater.models import Artist, Album, Song, AlbumCheckout, AlbumStatus

import django
from django.db.models import Q
django.setup()

class AlbumManager:

	def __init__(self, *args, **kwargs):

		# - everything in Bytes
		self.free_bytes_margin = int(kwargs['free_bytes_margin'])
		self.device_free_bytes = int(kwargs['device_free_bytes'])
		self.checkout_delta = 0
		self.albums_to_checkin = []
		self.albums_to_refresh = []
		self.albums_to_checkout = []

		albums_to_check_in = Album.objects.filter(action=Album.CHECKIN)
		logger.info("Registering %s previously marked albums to check-in.." % len(albums_to_check_in))
		self.checkin_albums(albums_to_check_in)

		requested_albums_to_check_out = Album.objects.filter(action=Album.REQUESTCHECKOUT, sticky=False)
		#logger.info("Registering %s previously requested albums to check-out.." % len(requested_albums_to_check_out))
		for album in requested_albums_to_check_out:
			if not self.checkout_album(album):
				logger.warn("Rejected checkout of %s/%s" % (album.artist.name, album.name))

		sticky_albums = Album.objects.filter(Q(albumcheckout__return_at__isnull=False) | Q(albumcheckout__isnull=True), sticky=True)
		#logger.info("Registering %s sticky albums to check-out.." % len(sticky_albums))
		for album in sticky_albums:
			if not self.checkout_album(album):
				logger.warn("Rejected checkout of sticky %s/%s" % (album.artist.name, album.name))

		albums_to_check_out = Album.objects.filter(action=Album.CHECKOUT, sticky=False)
		#logger.info("Registering %s previously marked albums to check-out.." % len(albums_to_check_out))
		for album in albums_to_check_out:
			if not self.checkout_album(album):
				logger.warn("Rejected checkout of %s/%s" % (album.artist.name, album.name))

		albums_to_refresh = Album.objects.filter(action=Album.REFRESH)
		#logger.info("Registering %s previously marked albums to refresh.." % len(albums_to_refresh))
		for album in albums_to_refresh:
			if not self.refresh_album(album):
				logger.warn("Rejected refresh of %s/%s" %(album.artist.name, album.name))

		am.send_status_to_logger()

	def send_status_to_logger(self):

		logger.info("Device Free: %s" % self.device_free_bytes)
		logger.info("Margin: %s" % self.free_bytes_margin)
		logger.info("Start: %s" % (self.device_free_bytes - self.free_bytes_margin))
		logger.info("	Removing: %s" % sum([ a.total_size for a in self.albums_to_checkin ]))
		logger.info("	Refreshing: %s" % sum([ a.total_size - a.old_total_size for a in self.albums_to_refresh ]))
		logger.info("	Adding: %s" % sum([ a.total_size for a in self.albums_to_checkout ]))
		logger.info("Current Delta: %s" % self.available_bytes())

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

	def refresh_album(self, album):

		delta = album.total_size - album.old_total_size
		
		if self.available_bytes() < delta:		
			logger.warn("Would-be free space: %s, Action is %s" %(self.available_bytes() - delta, Album.DONOTHING))	
			album.action = Album.DONOTHING
			album.save()
			return False

		album.action = Album.REFRESH
		album.save()

		self.albums_to_refresh.append(album)
		self.checkout_delta += delta

	def checkout_album(self, album):

		if self.available_bytes() < album.total_size:
			logger.warn("Would-be free space: %s, Action is %s" %(self.available_bytes() - album.total_size, Album.DONOTHING))	
			album.action = None
			album.save()
			return False
		
		album.action = Album.CHECKOUT
		album.save()

		self.albums_to_checkout.append(album)
		self.checkout_delta += album.total_size

		return True
		