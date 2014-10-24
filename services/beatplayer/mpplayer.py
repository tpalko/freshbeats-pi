#!/usr/bin/python2

import os
import sys
import traceback
import subprocess
import time
from SimpleXMLRPCServer import SimpleXMLRPCServer
import logging

logging.basicConfig(level=logging.DEBUG)

WORKING_FOLDER = "/mnt/beater_working"
PLAYLIST_FILE = "playlist.txt"
DEFAULT_VOLUME = 100

class MPPlayer():

	ps = None
	f_outw = None
	f_errw = None
	f_outr = None
	f_errr = None
	volume = None

	def __init__(self, *args, **kwargs):

		self.f_outw = file("mplayer.out", "wb")
		self.f_errw = file("mplayer.err", "wb")		

		self.f_outr = file("mplayer.out", "rb")
		self.f_errr = file("mplayer.err", "rb")		

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

			if not os.path.exists(os.path.join(WORKING_FOLDER, PLAYLIST_FILE)):
				logging.error("The playlist file is not accessible.")
				return

			logging.debug(options)
			
			do_shell=True
			shuffle = "-shuffle" if options['shuffle'] else ""
			command = "mplayer -ao alsa %s -slave -quiet -playlist %s" %(shuffle, os.path.join(WORKING_FOLDER, PLAYLIST_FILE))

			logging.debug(command)

			if self.ps:
				self.ps.kill()

			self.ps = subprocess.Popen(command, shell=do_shell, stdin=subprocess.PIPE, stdout=self.f_outw, stderr=self.f_errw)

			if self.volume is None:
				self.volume = DEFAULT_VOLUME

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

	m = MPPlayer()

	s = SimpleXMLRPCServer(('alarmpi',9000), allow_none=True)
	s.register_instance(m)
	logging.info("Serving forever on 9000..")
	s.serve_forever() # not!
