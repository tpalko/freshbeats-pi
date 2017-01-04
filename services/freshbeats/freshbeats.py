#!/usr/bin/python

import os
import sys
from os.path import join, getsize
import subprocess
import random
import logging
import traceback
import datetime
from ConfigParser import ConfigParser
import re
import math
from device import DeviceManager
from checkout import AlbumManager
import click
import hashlib

sys.path.append(os.path.join(os.path.dirname(__file__), '../../webapp'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'

#import config.settings_env
from beater.models import Artist, Album, Song, AlbumCheckout, AlbumStatus

# BUF_SIZE is totally arbitrary, change for your app!
BUF_SIZE = 65536  # lets read stuff in 64kb chunks!

import django
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
django.setup()

logging.basicConfig(
	level = logging.DEBUG
)
#fresh_logger = logging.StreamHandler()

logger = logging.getLogger('FreshBeats')

django_logger = logging.getLogger('django')
django_logger.setLevel(logging.INFO)

#name_logger = logging.getLogger(__name__)

'''
# mount -t vfat /dev/sdb /mnt/phone -o uid=1000,gid=1000,utf8,dmask=027,fmask=137

productid 
	708B - windows phone portal
	7089 - windows media sync
	7087 - usb mass storage
	7090 - charge only

Attaching the device to the computer will list it with the chosen function's productid under 'VBoxManage list usbhost' as 'busy'
The device will also show in virtualbox's settings/usb filter menu
Selecting it in the filter menu does nothing, until the VM is powered on, at which point it will be listed as 'captured'
Even after VM power off or removal of the filter, the device will remain 'captured' until virtualbox is closed and restarted

6/26/2015

Installed mtpfs (and gvfs may have already been installed).

gvfs-mount -li

will list all available virtual filesystems - when connected (at least via MTP) an Android device will show.

sudo mtpfs [mount point]

will detect MTP filesystems and do what it can to mount them.

e.g.

sudo mtpfs mtp:host=%5Busb%3A008%2C008%5D

device mounted at:
/run/user/1000/gvfs/mtp:host=%5Busb%3A008%2C008%5D/Internal storage

7/25/2015

plug in android device
ensure device is connected MTP
ensure device shows as mounted 
$ gvfs-mount -li | grep Android -A10
create mount point
$ sudo mkidr /media/android
mtpfs mount
$ sudo mtpfs -o allow_other /media/android

8/26/2015

https://wiki.cyanogenmod.org/w/Doc:_sshd

(going through SSH to device rather than MTP - works on wifi!)

but 'shell' user is really weak

1/16/2016

/storage/sdcard0 -> /storage/emulated/legacy (home folder)
/storage/emulated/legacy -> /mnt/shell/emulated/0

'''

class FreshBeats:

	device_mount = None
	dev = None

	def __init__(self):

		self.bytes_free = 0
		self.fail = 0

		config = ConfigParser()
		config.read(os.path.join(os.path.dirname(__file__), './config/settings.cfg'))

		for s in config.sections():
			self.__dict__ = dict(self.__dict__.items() + {i[0]: i[1] for i in config.items(s)}.items())

		self.device = DeviceManager(hostname=self.device_hostname, username=self.ssh_username)
		self.music_path = os.path.join(self.music_base_path, self.music_folder)

		if not os.path.exists(self.music_path):
			logger.error("Music path %s does not exist." %(self.music_path))
			exit(1)

	def report(self):

		logger.info("Report on device folder '%s'" % self.beats_target_folder)

		folders_on_device = self.device.get_music_folders_on_device(self.beats_target_folder)

		found_on_device = []
		#found_on_device_no_subfolder = []

		for folder_path in folders_on_device:
			
			#logger.debug("Folder found: %s" % folder_path)

			tup = folder_path.split('/')
			
			if len(tup) < 2:
				#found_on_device_no_subfolder.append(folder_path)
				continue
			
			artist = tup[-2]
			album = tup[-1]				
		
			artist_matches = Artist.objects.filter(name=artist)

			if len(artist_matches) > 1:
				logger.debug("Found %s artists for '%s'" % (len(artist_matches), artist))

			for artist_match in artist_matches:
				album_match = Album.objects.filter(artist__name=artist_match.name, name=album).first()
				if album_match:
					found_on_device.append(album_match)
					break

		'''
		if len(found_on_device_no_subfolder) > 0:
			logger.warn("%s folders found without proper structure to perform lookup" % len(found_on_device_no_subfolder))
			logger.warn(found_on_device_no_subfolder)
		'''
		
		if len(found_on_device) == 0:
			logger.warn("No albums found on device")
		else:

			max_album = max([ len(a.name.encode('utf-8')) for a in found_on_device ]) + 1
			max_artist = max([ len(a.artist.name.encode('utf-8')) for a in found_on_device ]) + 1

			logger.info("Albums on Device")

			for a in found_on_device:
				checked_out = a.current_albumcheckout() is not None 
				logger.info("{0:<{1}} {2:<{3}} {4:>32} {5:>10}".format(a.name.encode('utf-8'), max_album, a.artist.name.encode('utf-8'), max_artist, a.action, "checked-out" if checked_out else "-")) 

		action_albums = Album.objects.filter(~Q(action=Album.DONOTHING), action__isnull=False)
		if len(action_albums) > 0:
			max_album = max([ len(a.name.encode('utf-8')) for a in action_albums ]) + 1
			max_artist = max([ len(a.artist.name.encode('utf-8')) for a in action_albums ]) + 1
		checkout_size = sum([ a.total_size for a in action_albums.filter(Q(action=Album.CHECKOUT)) ])
		refresh_size = sum([ a.total_size - a.old_total_size for a in action_albums.filter(Q(action=Album.REFRESH)) ])
		checkin_size = sum([ a.total_size for a in action_albums.filter(action=Album.CHECKIN) ])
		
		logger.info("Albums in Plan")		
		for a in action_albums:
			logger.info("{0:<{1}} / {2:<{3}}: {4:>32}".format(a.name.encode('utf-8'), max_album, a.artist.name.encode('utf-8'), max_artist, a.action))

		logger.info("Checking out {0} MB".format(checkout_size/(1024*1024)))
		logger.info("Refreshing {0} MB".format(refresh_size/(1024*1024)))
		logger.info("Checking in {0} MB".format(checkin_size/(1024*1024)))
		logger.info("Net: {0} MB".format((checkout_size + refresh_size - checkin_size)/(1024*1024)))

	def update_db(self):

		try:

			for root, dirs, files in os.walk(self.music_path):

				if all(f in self.skip_files for f in files):
					logger.debug("	%s: all files skipped" % root)
					continue

				parts = root.split('/')

				album = parts[-1].strip()
				artist = parts[-2].strip()	

				logger.debug("%s / %s" %(artist, album))

				if '/'.join(parts[0:-2]) != self.music_path and artist != self.music_folder and '/'.join(parts) != self.music_path:
					logger.warn("	Path too deep - skipping - : %s" %('/'.join(parts)))
					continue

				all_files = files
				music_files = [ f for f in files if f[f.rfind("."):].lower() in self.music_file_extensions and f.find("._") < 0 ]
				#music_files = filter(lambda x: x[x.rfind("."):] in self.music_file_extensions and x.find("._") < 0, files)

				tracks = len(music_files)

				if tracks == 0:
					logger.debug("	No tracks - skipping")
					continue
					
				total_size = sum(getsize(join(root, name)) for name in all_files)
				audio_size = sum(getsize(join(root, name)) for name in music_files)

				# -- files in the root of the artist folder, i.e. not in an album folder
				if artist == self.music_folder:
					logger.debug("	Only one level deep - no album")
					artist = album
					album = 'no album'	
				
				artist_match = None

				try:
					artist_match = Artist.objects.get(name=artist)
				except Artist.DoesNotExist as d:
					pass

				if artist_match is None:

					logger.debug("	New Artist: %s" % artist)

					artist_match = Artist(name=artist)
					artist_match.save()

				possible_album_match = None
				updated_existing_album = False

				try:
					
					possible_album_match = Album.objects.get(artist=artist_match, name=album)

				except Album.DoesNotExist as d:

					pass # - it's OK

				if possible_album_match is None:

					logger.debug("	New Album: %s" % album)

					a = Album(artist=artist_match, name=album, tracks=0, total_size=total_size, audio_size=0, old_total_size=0, rating=Album.UNRATED)
					a.save()

				else:

					a = possible_album_match

					# - why True? forcing all albums to update?
					if int(a.tracks) != len(music_files) or int(a.total_size) != int(total_size) or int(a.audio_size) != int(audio_size):

						logger.debug("	Updating this album (hardcoded or for a following reason:)")

						if int(a.tracks) != len(music_files):
							logger.info("Track count: %s/%s" %(int(a.tracks), len(music_files)))
						if int(a.total_size) != int(total_size):
							logger.info("Total size: %s/%s" %(int(a.total_size), int(total_size)))
						if int(a.audio_size) != int(audio_size):
							logger.info("Audio size: %s/%s" %(int(a.audio_size), int(audio_size)))

						updated_existing_album = True

						a.tracks = 0
						a.old_total_size = a.total_size
						a.total_size = total_size
						a.audio_size = 0

						# - keep statuses!

						a.save()

						for song in a.song_set.all():
							song.delete()

				# - if new, or we made any changes to the album, rewrite the song records
				# - the songs were already cleared (above) if we updated and naturally empty if new
				if possible_album_match is None or updated_existing_album:

					for f in music_files:
						
						song_sha1sum = self._get_sha1sum(root, f)

						#logger.debug("%s: %s - %s" %(a.name, f.encode('utf-8'), song_sha1sum))

						s = Song(album=a, name=f, sha1sum=song_sha1sum)
						s.save()

						a.tracks += 1
						a.audio_size += getsize(join(root, f))

						a.save()

					if possible_album_match is None :
						logger.info("Inserted %s %s" %(artist, album))
					elif updated_existing_album:
						logger.info("Updated %s %s" %(artist, album))

			# - when we're all said and done adding, delete albums that cannot be found on disk (if they've never been checked-out)
			albums = Album.objects.filter(albumcheckout__isnull=True)

			for a in albums:

				if not os.path.exists(self._get_storage_path(a)):
					a.delete()
					logger.info("Deleted %s %s" %(a.artist, a.name))

		except:

			message = str(sys.exc_info()[1])

			logging.error(str(sys.exc_info()[0]))
			logging.error(message)
			traceback.print_tb(sys.exc_info()[2])

	def _get_sha1sum(self, root, filename):

		sha1 = hashlib.sha1()

		with open(join(root, filename), 'rb') as f:
		    while True:
		        data = f.read(BUF_SIZE)
		        if not data:
		            break
		        sha1.update(data)

		song_sha1sum = sha1.hexdigest()
		
		return song_sha1sum

	def mark_albums(self):

		device_free_bytes = self.device.get_free_bytes()
		margin = int(self.free_space_mb)*1024*1024
		am = AlbumManager(free_bytes_margin=margin, device_free_bytes=device_free_bytes)

		# - we want to keep at least one mix-it-up-rated album
		# - if we aren't renewing one, pick one to check out
		any_kept_mixins = Album.objects.filter(action__in=[Album.DONOTHING, Album.REFRESH], rating=Album.MIXITUP, albumcheckout__isnull=False, albumcheckout__return_at__isnull=True).exists()
		
		if not any_kept_mixins:

			new_mixins = Album.objects.filter((Q(albumcheckout__isnull=True) | (Q(albumcheckout__isnull=False) & Q(albumcheckout__return_at__isnull=False))), rating=Album.MIXITUP)
			new_mixin_list = list(new_mixins)				

			if len(new_mixin_list) > 0:
				new_mixin = random.choice(new_mixin_list)
				logger.info("Registering a mix-it-up album...")
				if not am.checkout_album(new_mixin):
					logger.warn("Rejected checkout of %s/%s" % (new_mixin.artist.name, new_mixin.name))

		loveit_albums = Album.objects.filter(rating=Album.LOVEIT, action=None)
		never_checked_out_albums = Album.objects.filter(albumcheckout__isnull=True, action=None)
		unrated_albums = Album.objects.filter(rating=Album.UNRATED, action=None, albumstatus__isnull=True)
		
		album_lists = [loveit_albums, never_checked_out_albums, unrated_albums]

		fails = 10

		while True:
			random_list = random.choice(album_lists)
			if len(random_list) == 0:
				album_lists.remove(random_list)
				continue
			album = random.choice(random_list)
			logger.info("Registering a random album...")
			if not am.checkout_album(album):
				fails = fails - 1
				logger.warn("Rejected checkout of %s/%s - attempts left: %s" % (album.artist.name, album.name, fails))				
			if fails <= 0:
				break

		am.send_status_to_logger()

	def copy_files(self):

		remove_albums = Album.objects.filter(action=Album.CHECKIN)

		for r in remove_albums:
			self.remove_album(r)

		refresh_albums = Album.objects.filter(action=Album.REFRESH)

		for u in refresh_albums:
			self.remove_album(u)
			self.copy_album_to_device(u)

		add_albums = Album.objects.filter(action=Album.CHECKOUT)

		for a in add_albums:
			self.copy_album_to_device(a)

	def remove_album(self, a):

		logger.info("removing: %s %s" %(a.artist.name, a.name))

		rm_statement = ['ssh', '%s@%s' % (self.ssh_username, self.device_hostname), 'rm -rf "%s"' %(join(self.device_mount, self.beats_target_folder, a.artist.name, a.name))]
		ps = subprocess.Popen(rm_statement)
		(out,err,) = ps.communicate(None)

		logger.info("Remove code: %s" % ps.returncode)

		if ps.returncode == 0:
			current_checkout = a.current_albumcheckout()
			if current_checkout:
				current_checkout.return_at = timezone.now()
				current_checkout.save()
			else:
				logger.warn("removing, but not checked out????")
			a.action = None
			a.save()

	def pull_photos(self):

		pull_pairs = zip(self.sources.split(','), self.targets.split(','))

		for source, target in pull_pairs:

			logger.info("Copying %s to %s" %(source, target))
			source_uri = '%s@%s:%s' %(self.ssh_username, self.device_hostname, source)

			copy_statement = ['scp', '-r', '-p', source_uri, target]
			ps = subprocess.Popen(copy_statement, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			(out,err,) = ps.communicate(None)

			logger.info(out)

			if err:				
				logger.error(err)

			logger.debug("Copy code: %s" % ps.returncode)

	def copy_album_to_device(self, a):

		artist_folder = os.path.join(self.beats_target_folder, a.artist.name) #join(self.device_mount, self.beats_target_folder, a.artist)
		
		logger.info("adding folder: %s" %(artist_folder))

		mkdir_statement = ['ssh', '%s@%s' %(self.ssh_username, self.device_hostname), 'mkdir -p "%s"' % artist_folder]
		logger.info(mkdir_statement)
		
		ps = subprocess.Popen(mkdir_statement, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		(out,err,) = ps.communicate(None)

		logger.debug('out: %s' % out)
		logger.debug('err: %s' % err)

		cp_statement = ['scp', '-r', self._get_storage_path(a), '%s@%s:"%s"' %(self.ssh_username, self.device_hostname, artist_folder)]
		logger.info(cp_statement)

		ps = subprocess.Popen(cp_statement, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		(out,err,) = ps.communicate(None)

		logger.debug('out: %s' % out)
		logger.debug('err: %s' % err)

		logger.info("Add code: %s" % ps.returncode)

		if ps.returncode == 0:
			ac = AlbumCheckout(album=a, checkout_at=timezone.now())
			ac.save()
			a.action = None
			a.save()

	def _get_storage_path(self, album):

		if album.name == 'no album':
			return join(self.music_base_path, self.music_folder, album.artist.name)

		return join(self.music_base_path, self.music_folder, album.artist.name, album.name)

@click.command()
@click.option('--ingest', '-i', is_flag=True, help='Ingest new music on disk.')
@click.option('--mark', '-m', is_flag=True, help='Mark albums for copy.')
@click.option('--report', '-r', is_flag=True, help='Report on device status and copy plan.')
@click.option('--apply', '-a', is_flag=True, help='Apply copy plan to device.')
@click.option('--pictures', '-p', is_flag=True, help='Pull pictures from device.')
def main(ingest, mark, report, apply, pictures):

	f = FreshBeats()

	if ingest:
		f.update_db()
	
	if mark:
		f.mark_albums()
	
	if apply:
		f.copy_files()

	if report:
		f.report()

	if pictures:
		f.pull_photos()

if __name__ == "__main__":
	main()