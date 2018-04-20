from os.path import join, getsize
import shlex
import subprocess
import logging
import re
import math

logging.basicConfig(level = logging.DEBUG)
logger = logging.getLogger('DeviceManager')

class DeviceManager:

	hostname = None
	username = None

	def __init__(self, *args, **kwargs):
		self.hostname = kwargs['hostname']
		self.username = kwargs['username']	

	def remove_album(self, a):

		logger.info("removing: %s %s" %(a.artist, a.name))

		rm_statement = ['ssh', '%s@%s', '\'rm -rf %s\'' % join(self.device_mount, self.beats_target_folder, a.artist, a.name)]
		ps = subprocess.Popen(rm_statement)
		(out,err,) = ps.communicate(None)

		logger.info("Remove code: %s" % ps.returncode)

		if ps.returncode == 0:
			current_checkout = a.current_albumcheckout()
			current_checkout.return_at = datetime.datetime.now()
			current_checkout.save()
			a.action = None
			a.save()

	def pull_photos(self):

		copy_statement = ['scp', join(self.photos_device_folder, '*'), self.photos_inbox_folder]
		ps = subprocess.Popen(copy_statement, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		(out,err,) = ps.communicate(None)

		logger.debug('out: %s' % out)
		logger.debug('err: %s' % err)

		logger.info("Copy code: %s" % ps.returncode)

	def copy_album_to_device(self, a):

		artist_folder = os.path.join(self.beats_target_folder, a.artist.name) #join(self.device_mount, self.beats_target_folder, a.artist)
		
		logger.info("adding folder: %s" %(artist_folder))

		mkdir_statement = ['ssh', '%s@%s' %(self.username, self.hostname), '\'mkdir -p "%s"\'' % artist_folder]
		logger.info(mkdir_statement)
		
		ps = subprocess.Popen(mkdir_statement, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		(out,err,) = ps.communicate(None)

		logger.debug('out: %s' % out)
		logger.debug('err: %s' % err)

		cp_statement = ['scp', '-r', self._get_storage_path(a), '%s@%s:"%s"' %(self.username, self.hostname, artist_folder)]
		logger.info(cp_statement)

		ps = subprocess.Popen(cp_statement, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		(out,err,) = ps.communicate(None)

		logger.debug('out: %s' % out)
		logger.debug('err: %s' % err)

		logger.info("Add code: %s" % ps.returncode)

		if ps.returncode == 0:
			ac = AlbumCheckout(album=a, checkout_at=datetime.datetime.now())
			ac.save()
			a.action = None
			a.save()

	def get_music_folders_on_device(self, target_folder):

		find_folders_command = shlex.split("ssh %s@%s 'find %s -type d'" %(self.username, self.hostname, target_folder))
		logger.info(find_folders_command)

		ps = subprocess.Popen(find_folders_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) #, shell=True, executable='/bin/bash')

		(out, err,) = ps.communicate(None)

		if err:
			logger.error(err)

		folders = [ f.replace("%s/" % target_folder, '') for f in out.split('\n') if f and f != target_folder ]

		return folders

	def get_free_bytes(self):

		#ps = subprocess.Popen('df -k'.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		#ps = subprocess.Popen(('grep ' + self.device_mount).split(' '), stdin=ps.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

		df_cmd = 'ssh %s@%s \'df\'' %(self.username, self.hostname)
		grep_emulated = 'grep emulated'
		
		ps = subprocess.Popen(df_cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		ps = subprocess.Popen(grep_emulated.split(' '), stdin=ps.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		
		(out, err,) = ps.communicate(None)

		if out:
			logger.error(out)

		if err:
			logger.error(err)

		# - Filesystem               Size     Used     Free   Blksize
		# - /mnt/shell/emulated     12G     8.5G     3.5G   4096
		parts = [ p for p in out.split(' ') if p != '' ]
		free = parts[3]

		match = re.search('([0-9\.]+)([A-Z])', free)

		size = match.group(1)
		unit = match.group(2)

		unit_multiplier = { 'G': math.pow(1024, 3), 'M': math.pow(1024, 2), 'K': math.pow(1024, 1) }

		size_in_bytes = int(math.floor(float(size)*unit_multiplier[unit]))

		logger.debug("free space: %s (%s bytes)" % (free, size_in_bytes))
		
		return size_in_bytes
