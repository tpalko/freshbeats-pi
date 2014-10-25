#!/usr/bin/python

import os
import sys
from os.path import join, getsize
import subprocess
import random
import logging
import traceback
import datetime

# - let's use the database configuration the webapp already has defined..
sys.path.append('../../webapp')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import config.settings
from beater.models import Album, Song, AlbumCheckout, AlbumStatus

logger = logging.getLogger('FreshBeats')
fresh_logger = logging.StreamHandler()

logger.setLevel(logging.DEBUG)
logger.addHandler(fresh_logger)

# mount -t vfat /dev/sdb /mnt/phone -o uid=1000,gid=1000,utf8,dmask=027,fmask=137

MUSIC_FOLDER = 'music'
ARTIST_PATH = '/media/storage/%s' %(MUSIC_FOLDER)
BEATS_TARGET = 'freshbeats'
FREE_SPACE_MARGIN = 100*1024*1024 # - in bytes
MAX_FAIL = 10

skip_files = ['desktop.ini', '.DS_Store']

class FreshBeats:

	args = None
	device_mount = None

	def __init__(self, args, device_mount):

		self.bytes_free = 0
		self.fail = 0

		self.args = args
		self.device_mount = device_mount

	def update_db(self):

		try:

			for root, dirs, files in os.walk(ARTIST_PATH):

				if all(f in skip_files for f in files):
					continue

				parts = root.split('/')
				
				album = parts[-1].strip()
				artist = parts[-2].strip()	

				all_files = files
				music_files = filter(lambda x: x[x.rfind("."):] in ['.mp3', '.m4a', '.MP3', '.WMA', '.wav', '.WAV'] and x.find("._") < 0, files)

				tracks = len(music_files)

				if tracks == 0:
					continue
					
				total_size = sum(getsize(join(root, name)) for name in all_files)
				audio_size = sum(getsize(join(root, name)) for name in music_files)

				# -- files in the root of the artist folder, i.e. not in an album folder
				if artist == MUSIC_FOLDER:
					artist = album
					album = 'no album'	

				possible_match = None
				updated_existing = False

				try:
					
					possible_match = Album.objects.get(artist=artist, name=album)

				except Album.DoesNotExist as d:

					pass # - it's OK

				if possible_match is None:

					a = Album(artist=artist, name=album, tracks=0, total_size=0, audio_size=0, old_total_size=0, rating=Album.UNRATED)
					a.save()

				else:

					a = possible_match

					if int(a.tracks) != len(music_files) or int(a.total_size) != int(total_size) or int(a.audio_size) != int(audio_size):

						updated_existing = True

						a.tracks = 0
						a.old_total_size = a.total_size
						a.total_size = total_size
						a.audio_size = 0

						# - keep statuses

						a.save()

						for song in a.song_set.all():
							song.delete()

				if possible_match is None or updated_existing:

					for f in music_files:
			
						s = Song(album=a, name=f)
						s.save()

						a.tracks += 1
						a.audio_size += getsize(join(root, f))

						a.save()

					if possible_match is None :
						logger.debug("Inserted %s %s" %(artist, album))
					elif updated_existing:
						logger.debug("Updated %s %s" %(artist, album))

			albums = Album.objects.filter(albumcheckout__isnull=True)

			for a in albums:

				if not os.path.exists(self._get_storage_path(a)):
					a.delete()
					logger.debug("Deleted %s %s" %(a.artist, a.name))

		except:

			logging.error(sys.exc_info())
			traceback.print_tb(sys.exc_info()[2])

	def mark_albums(self):

		device_free_space = self._get_space()

		albums_to_remove = Album.objects.filter(action=Album.REMOVE)
		remove_size = 0

		if len(albums_to_remove) > 0:
			remove_size = reduce(lambda a, b: a + b, map(lambda a: a.total_size, albums_to_remove))
		
		albums_to_update = Album.objects.filter(action=Album.UPDATE)
		update_size = 0

		if len(albums_to_update) > 0:
			update_size = reduce(lambda a, b: a + b, map(lambda a: a.total_size - a.old_total_size, albums_to_update))

		albums_to_add = Album.objects.filter(action=Album.ADD)
		add_size = 0

		if len(albums_to_add) > 0:
			add_size = reduce(lambda a, b: a + b, map(lambda a: a.total_size, albums_to_add))	

		self.bytes_free = device_free_space - FREE_SPACE_MARGIN + remove_size - update_size - add_size

		logger.debug("bytes free: %s (free %s margin %s remove %s update %s add %s)" %(self.bytes_free, device_free_space, FREE_SPACE_MARGIN, remove_size, update_size, add_size))

		albums_previously_checked_out_query = "select a.* " + \
			"from beater_album a " + \
			"inner join (" + \
				"select a.id, sum(isnull(ac.return_at)), count(*) " + \
				"from beater_album a " + \
				"inner join beater_albumcheckout ac on ac.album_id = a.id " + \
				"group by a.id " + \
				"having sum(isnull(ac.return_at)) = 0 " + \
				"and count(*) > 0) checkouts on checkouts.id = a.id " +  \
			"where a.action is null " +  \
			"and a.rating in %s"

		checked_out_mixitups = Album.objects.filter(rating=Album.MIXITUP, albumcheckout__isnull=False, albumcheckout__return_at__isnull=True)
		kept_mixins = map(lambda c: c.action in [Album.DONOTHING, Album.UPDATE], checked_out_mixitups)

		if not any(kept_mixins):

			new_mixins = Album.objects.raw(albums_previously_checked_out_query, [Album.MIXITUP])
			new_mixin_list = list(new_mixins)				

			if len(new_mixin_list) > 0:

				new_mixin = random.choice(new_mixin_list)
				self._mark_album_for_add(new_mixin)

		while self.bytes_free > 0 and self.fail < MAX_FAIL:			

			new_add = None

			if random.choice(range(0,30)) == 14:
				
				new_loveits = Album.objects.raw(albums_previously_checked_out_query, [Album.LOVEIT, Album.UNDECIDED])
				new_loveit_list = list(new_loveits)

				if len(new_loveit_list) > 0:
					new_add = random.choice(new_loveit_list)

			if new_add is None:

				albums_never_checked_out = self._get_albums_never_checked_out()

				if len(albums_never_checked_out) > 0:
					new_add = random.choice(albums_never_checked_out)

			if new_add is None:
				break

			self._mark_album_for_add(new_add)

		ressurection_bin = [Album.LOVEIT, Album.MIXITUP]

		for r in ressurection_bin:

			removeds = self._get_albums_currently_checked_out(r)

			while self.bytes_free > 0 and self.fail < MAX_FAIL:
				removed = random.choice(removeds)
				self._mark_album_for_add(removed, only_update=True)	

	def update_device(self):

		while True:
		
			action_albums = Album.objects.filter(action__isnull=False)

			if len(action_albums) > 0:

				action_album = random.choice(action_albums)

				if action_album.action == Album.REMOVE:

					self._remove_album(action_album)

				elif action_album.action == Album.UPDATE:

					self._remove_album(action_album)
					self._add_album(action_album)

				elif action_album.action == Album.ADD:

					self._add_album(action_album)			

			else:

				break

	def _get_albums_never_checked_out(self):
		return Album.objects.filter(albumcheckout__isnull=True, action__isnull=True)

	def _get_albums_currently_checked_out(self, rating):
		return Album.objects.filter(albumcheckout__isnull=False, albumcheckout__return_at__isnull=True, rating=rating, action=Album.REMOVE)

	def _get_storage_path(self, album):

		if album.name == 'no album':
			return join(ARTIST_PATH, album.artist)

		return join(ARTIST_PATH, album.artist, album.name)

	def _mark_album_for_add(self, album, only_update=False):

		if album.total_size < self.bytes_free:
			album.action = Album.ADD
			if only_update:
				album.action = Album.UPDATE if album.is_updatable() else Album.DONOTHING			
			album.save()
			self.bytes_free = self.bytes_free - album.total_size
			logger.debug("bytes free: %s" %(self.bytes_free))
		else:
			self.fail = self.fail + 1

	def _get_albums_never_checked_out(self):
		return Album.objects.filter(albumcheckout__isnull=True, action__isnull=True)

	def _get_albums_currently_checked_out(self, rating):
		return Album.objects.filter(albumcheckout__isnull=False, albumcheckout__return_at__isnull=True, rating=rating, action=Album.REMOVE)

	def _get_storage_path(self, album):
		return join(ARTIST_PATH, album.artist, album.name)

	def _mark_album_for_add(self, album, only_update=False):

		if album.size < self.bytes_free:
			album.action = Album.ADD
			if only_update:
				album.action = Album.UPDATE if album.is_updatable() else Album.DONOTHING			
			album.save()
			self.bytes_free = self.bytes_free - album.size
			logger.debug("bytes free: %s" %(self.bytes_free))
		else:
			self.fail = self.fail + 1

	def _remove_album(self, a):

		logger.debug("removing: %s %s" %(a.artist, a.name))

		rm_statement = ['rm', '-rf', join(self.device_mount, BEATS_TARGET, a.artist, a.name)]
		ps = subprocess.Popen(rm_statement)
		(out,err,) = ps.communicate(None)

		if ps.returncode == 0:
			current_checkout = a.current_albumcheckout()
			current_checkout.return_at = datetime.datetime.now()
			current_checkout.save()
			a.action = None
			a.save()

	def _add_album(self, a):

		logger.debug("adding: %s %s" %(a.artist, a.name))

		cp_statement = ['cp', '-R', self._get_storage_path(a), join(self.device_mount, BEATS_TARGET, a.artist)]								
		ps = subprocess.Popen(cp_statement)
		(out,err,) = ps.communicate(None)

		if ps.returncode == 0:
			ac = AlbumCheckout(album=a, checkout_at=datetime.datetime.now())
			ac.save()
			a.action = None
			a.save()

	def _get_space(self):

		ps = subprocess.Popen('df -k'.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		ps = subprocess.Popen(('grep ' + self.device_mount).split(' '), stdin=ps.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

		(out, err,) = ps.communicate(None)

		parts = filter(lambda p: p != '', out.split(' '))

		print parts
		
		# result listed in KB, we want bytes
		return int(parts[3]) * 1024

	def freshen(self):

		for a in self.args:
			method = getattr(self, a)
			if method is not None:
				method()

if __name__ == "__main__":

	args = {}
	device_mount = None

	for i,a in enumerate(sys.argv[1:]):		
		if a == "--devicemount":
			device_mount = sys.argv[i+2]
		elif a[0:2] == "--":
			args[a[2:]] = True

	f = FreshBeats(args, device_mount)
	f.freshen()
