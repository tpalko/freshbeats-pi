#!/usr/bin/python2

import os
import socket
import sys
import traceback
import subprocess
import time
from SimpleXMLRPCServer import SimpleXMLRPCServer
import logging
import ConfigParser

logging.basicConfig(level=logging.DEBUG)

class MPPlayer():

	ps = None
	f_outw = None
	f_errw = None
	f_outr = None
	f_errr = None
	volume = None
	default_volume = 100
	playlist_filepath = None

	def __init__(self, env, *args, **kwargs):

		self.f_outw = file("mplayer.out", "wb")
		self.f_errw = file("mplayer.err", "wb")		

		self.f_outr = file("mplayer.out", "rb")
		self.f_errr = file("mplayer.err", "rb")		

		self.config = ConfigParser.ConfigParser()
		config_file = "./config/settings_%s.cfg" %(env)

		if not os.path.exists(config_file):
			raise Exception("Config file '%s' not found" %(config_file))

		self.config.read(config_file)

		working_folder = self.config.get('paths', 'PLAYLIST_WORKING_FOLDER')
		filename = self.config.get('paths', 'PLAYLIST_FILENAME')
		self.playlist_filepath = os.path.join(working_folder, filename)
		
		self.default_volume = self.config.get('player', 'DEFAULT_VOLUME')

	def get_player_info(self):

		try:

			self.f_outr.seek(0)
			lines = list(self.f_outr)

			info = {}
			labels = ["Playing ", " Title: ", " Artist: ", " Album: ", " Year: ", " Comment: ", " Track: ", " Genre: "]

			for l in lines:

				for b in labels:

					if l.find(b) == 0:
						info[b.strip().replace(':', '')] = l[len(b):len(l)].strip().replace('\n', '')

			return info
		except:
			logging.error(sys.exc_info())
			traceback.print_tb(sys.exc_info()[2])

	def play(self, options={}):#, match=None):

		try:

			if not os.path.exists(self.playlist_filepath):
				logging.error("The playlist file is not accessible.")
				return

			logging.debug(options)
			
			do_shell=True
			shuffle = "-shuffle" if options['shuffle'] else ""
			command = "mplayer -ao alsa %s -slave -quiet -playlist %s" %(shuffle, self.playlist_filepath)

			logging.debug(command)

			if self.ps:
				self.ps.kill()

			self.ps = subprocess.Popen(command, shell=do_shell, stdin=subprocess.PIPE, stdout=self.f_outw, stderr=self.f_errw)

			if self.volume is None:
				self.volume = self.default_volume

			self._issue_command("volume %s 1" %(self.volume))

			'''
			Playing /mnt/music/Unknown artist/George Harrison/Unknown album (6-1-2014 11-17-24 PM)_03_Track 3.mp3.
			libavformat version 55.33.100 (internal)
			Audio only file format detected.
			Clip info:
			 Title: Track 3                       
			 Artist:                               
			 Album: Unknown album (6/1/2014 11:17:
			 Year:     
			 Comment:                             
			 Track: 3
			 Genre: Unknown
			'''
		except:

			logging.error(sys.exc_info())
			traceback.print_tb(sys.exc_info()[2])

	def pause(self):
		
		self._issue_command("pause")

	def stop(self):
		
		self._issue_command("stop")

	def mute(self):

		try:

			#self.mute = False if self.mute else True

			#logging.debug("changed mute to %s" %(self.mute))
			
			self._issue_command("mute") # %s" %("1" if self.mute else "0"))
			self._issue_command("volume %s 1" %(self.volume))

		except:

			logging.error(sys.exc_info())
			traceback.print_tb(sys.exc_info()[2])

	def next(self):

		self._issue_command("pt_step 1")

	def _issue_command(self, command):

		logging.debug("issuing %s" %(command))
		self.ps.stdin.write("%s\n" %(command))

if __name__ == "__main__":

	if len(sys.argv) > 1 and sys.argv[1] not in ['dev', 'prod']:
		print "Usage: "
		print "%s %s" %(sys.argv[0], ['dev', 'prod'])
		sys.exit(1)

	env = 'dev'

	if len(sys.argv) > 1:
		env = sys.argv[1]

	m = MPPlayer(env=env)

	s = SimpleXMLRPCServer(('localhost',9000), allow_none=True)
	s.register_instance(m)
	logging.info("Serving forever on 9000..")
	s.serve_forever() # not!
