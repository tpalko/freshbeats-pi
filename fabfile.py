import fabric
from fabric.api import *

env.user = 'root'
env.host_string = '192.168.1.11'
env.password = 'root'

def play():

	with cd('/mnt/music'):
		run('mplayer -ao alsa -shuffle -playlist playlist.txt &')


	
