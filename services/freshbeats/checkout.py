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

	def status(self):

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
			
			album.action = Album.REMOVE
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
		
		album.action = Album.ADD
		album.save()

		self.albums_to_checkout.append(album)
		self.checkout_delta += album.total_size

		return True
		