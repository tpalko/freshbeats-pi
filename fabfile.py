import fabric
from fabric.api import *

env.user = 'root'
env.host_string = '192.168.1.11'
env.password = 'root'

def play():

	with cd('/mnt/music'):
		run('mplayer -ao alsa -shuffle -playlist playlist.txt &')

def deploy_beatplayer():

	env.user = 'root'
	env.password = 'root'
	env.host_string = 'alarmpi'

	run('rm -rf /usr/share/freshbeats/services/beatplayer')
	run('mkdir -p /usr/share/freshbeats/services/')
	put('services/beatplayer', '/usr/share/freshbeats/services/')
	