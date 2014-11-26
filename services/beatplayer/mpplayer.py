#!/usr/bin/python2

import os
import socket
import sys
import traceback
import subprocess
import time
from SimpleXMLRPCServer import SimpleXMLRPCServer
import logging
from optparse import OptionParser
from ConfigParser import ConfigParser

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MPPlayer():

	ps = None
	volume = None

	def __init__(self, env, *args, **kwargs):

		self.f_outw = file("mplayer.out", "wb")
		self.f_errw = file("mplayer.err", "wb")		

		self.f_outr = file("mplayer.out", "rb")
		self.f_errr = file("mplayer.err", "rb")		

		config_file = os.path.join(os.path.dirname(__file__), "./config/settings_%s.cfg" %(env))

		if not os.path.exists(config_file):
			raise Exception("Config file '%s' not found" %(config_file))

		config = ConfigParser()
		config.read(config_file)

		for s in config.sections():
			self.__dict__ = dict(self.__dict__.items() + {i[0]: i[1] for i in config.items(s)}.items())

		self.playlist_filepath = os.path.join(self.playlist_working_folder, self.playlist_filename)

		logger.debug("Using %s for playlist" % self.playlist_filepath)
		
	def get_music_folder(self):
		return self.music_folder

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
			logger.error(sys.exc_info())
			traceback.print_tb(sys.exc_info()[2])

	def play(self, options={}):#, match=None):

		try:

			if not os.path.exists(self.playlist_filepath):
				logger.error("The playlist file %s is not accessible." % self.playlist_filepath)
				return

			logger.debug(options)
			
			do_shell=True
			shuffle = "-shuffle" if 'shuffle' in options and options['shuffle'] else ""
			command = "mplayer -ao alsa %s -slave -quiet -playlist %s" %(shuffle, self.playlist_filepath)

			logger.debug(command)

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

			logger.error(sys.exc_info())
			traceback.print_tb(sys.exc_info()[2])

	def pause(self):
		
		self._issue_command("pause")

	def stop(self):
		
		self._issue_command("stop")

	def mute(self):

		try:

			#self.mute = False if self.mute else True

			#logger.debug("changed mute to %s" %(self.mute))
			
			self._issue_command("mute") # %s" %("1" if self.mute else "0"))
			self._issue_command("volume %s 1" %(self.volume))

		except:

			logger.error(sys.exc_info())
			traceback.print_tb(sys.exc_info()[2])

	def next(self):

		self._issue_command("pt_step 1")

	def _issue_command(self, command):

		if self.ps is None:
			raise Exception("Player process is not started.")

		logger.debug("issuing %s" %(command))
		self.ps.stdin.write("%s\n" %(command))

if __name__ == "__main__":

	parser = OptionParser(usage='usage: %prog [options]')

	parser.add_option("-e", "--environment", dest="environment", default='dev', help="environment (dev/prod)")
	parser.add_option("-a", "--address", dest="address", default='127.0.0.1', help="IP address on which to listen")
	parser.add_option("-p", "--port", dest="port", default='9000', help="port on which to listen")

	(options, args) = parser.parse_args()

	m = MPPlayer(env=options.environment)

	s = SimpleXMLRPCServer((options.address, int(options.port)), allow_none=True)
	s.register_instance(m)
	logger.info("Serving forever on %s:%s.." %(options.address, options.port))
	s.serve_forever() # not
