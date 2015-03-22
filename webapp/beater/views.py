from django.shortcuts import render
from django.shortcuts import render_to_response
from django.shortcuts import redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.conf import settings
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import os
import sys
from models import Album, AlbumCheckout, Song, AlbumStatus, PlaylistSong
import xmlrpclib
import logging
import traceback
import json
import random
import socket
import requests
import re

#logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)
fresh_logger = logging.StreamHandler()

logger.setLevel(logging.DEBUG)
logger.addHandler(fresh_logger)

logger.debug("Setting path for RPi: %s" % settings.BEATPLAYER_SERVER)
p = xmlrpclib.ServerProxy(settings.BEATPLAYER_SERVER)

#logger.debug("Setting callback for RPi")
#p.set_callback("http://%s:%s/player_complete" %(settings.BEATER_HOSTNAME, settings.BEATER_PORT))

try:
	logger.debug("Calling to get music folder")
	beatplayer_music_folder = p.get_music_folder()
	logger.debug("Music folder found: %s" % beatplayer_music_folder)
except:
	logger.error("Music folder NOT found")

PLAYER_STATE_STOPPED = 'stopped'
PLAYER_STATE_PLAYING = 'playing'
PLAYER_STATE_PAUSED = 'paused'

mute = False
shuffle = False
playlist = True

'''
			 | shuffle off 				| shuffle on 		|
-------------------------------------------------------------
playlist off | no play					| any song 			|
playlist on  | playlist after current 	| playlist unplayed |

'''

player_state = PLAYER_STATE_STOPPED

# - PAGES

def home(request):

	albums = Album.objects.all()

	alphabet = set([name[0] for name in [re.sub('[\(\)\.]', '', album.artist).lower() for album in albums]])
	alphabet = sorted(alphabet, cmp=lambda x,y: cmp(x.lower(), y.lower()))

	return render_to_response('home.html', { 'alphabet': alphabet }, context_instance=RequestContext(request))

def survey(request):

	albums = Album.objects.filter(action=None, albumcheckout__isnull=False, albumcheckout__return_at=None)

	if len(albums) == 0:
		return redirect('beater.views.home')

	return render_to_response('survey.html', 
		{ 
			'album': random.choice(albums), 
			'rating_choices': Album.ALBUM_RATING_CHOICES, 
			'status_choices': AlbumStatus.ALBUM_STATUS_CHOICES 
		}, 
		context_instance=RequestContext(request))

def album(request, albumid):

	album = Album.objects.get(pk=albumid)

	return render_to_response('album.html', { 'album': album, 'songs': album.song_set.all() }, context_instance=RequestContext(request))

# - PARTIALS

def album_filter(request, filter):

	search = request.GET.get('search')

	albums = []

	if filter == 'all':
		albums = Album.objects.order_by('artist', 'name').filter(~Q(albumstatus__status=AlbumStatus.INCOMPLETE))
	elif filter == 'checkedout':
		albums = Album.objects.order_by('artist', 'name').filter(albumcheckout__isnull=False, albumcheckout__return_at=None)
	elif filter == 'playlist':
		albums = Album.objects.order_by('artist', 'name').filter(playlistsong__id__isnull=False)
	elif filter == AlbumStatus.INCOMPLETE:
		albums = Album.objects.order_by('artist', 'name').filter(albumstatus__status=AlbumStatus.INCOMPLETE)
	elif filter == AlbumStatus.MISLABELED:
		albums = Album.objects.order_by('artist', 'name').filter(albumstatus__status=AlbumStatus.MISLABELED)

	return render_to_response('_albums.html', { 'albums':albums }, context_instance=RequestContext(request))

def album_letter(request, letter):

	albums = Album.objects.all()
	albums = filter(lambda a: a.artist[0].lower() == letter, albums)

	return render_to_response('_albums.html', { 'albums':albums }, context_instance=RequestContext(request))

# - ENDPOINTS

@csrf_exempt
def command(request, type):
	if type == "album":
		return album_command(request)
	elif type == "player":
		return player_command(request)

@csrf_exempt
def album_command(request):

	response = {}

	album = Album.objects.get(pk=request.POST.get('albumid'))
	command = request.POST.get('command')

	if command == "keep":

		album.action = Album.DONOTHING
		album.save()
		response['albumid'] = album.id

	return HttpResponse(json.dumps(response))

@csrf_exempt
def survey_post(request):

	album = Album.objects.get(pk=request.POST.get('albumid'))
	#albumcheckout = album.current_albumcheckout()

	album.rating = request.POST.get('rating')

	if request.POST.get('keep', 0) == 0:
		album.action = Album.REMOVE
	elif album.is_updatable():
		album.action = Album.UPDATE
	else:
		album.action = Album.DONOTHING

	new_statuses = request.POST.get('statuses', None)

	if new_statuses is not None:
		print new_statuses
		new_statuses = new_statuses.split(',')
		album.replace_statuses(new_statuses)

	album.save()

	return HttpResponse()

#@require_http_methods(["POST"])

@csrf_exempt
def player_command(request):
	
	response = {}
	
	try:

		problem = None
		player_info = None

		command = request.POST.get('command', None) # surprise, playlist, next, shuffle, enqueue_album, play/enqueue_song, pause, stop, mute, keep
		albumid = request.POST.get('albumid', None)
		songid = request.POST.get('songid', None)

		enqueue = command.split('_')[0] == "enqueue"
		play = command.split('_')[0] == "play"

		logger.debug("Got command: %s" % command)
	
		response = _handle_command(command, albumid, songid, enqueue, play, force_play=True)		

	except:		
		logger.error(sys.exc_info()[1])
		traceback.print_tb(sys.exc_info()[2])
		_publish_event('alert', json.dumps({'message': str(sys.exc_info()[1])}))

	return HttpResponse(json.dumps(response))

@csrf_exempt
def player_complete(request):
	'''
	Ultra weirdness here..
	If 'force_play' is false..
	When beatplayer would return from a song prematurely and call this callback, it would fetch the next song and issue the play call, but it would be rejected..
	Because even though beatplayer returned prematurely, the process was still alive.
	So 'next' worked..
	The natural return at the end of a song also worked, because at that point the process was dead, so it didn't need to be forced.
	'''

	try:

		logger.debug("Player complete")

		#if player_state == PLAYER_STATE_PLAYING:
		response = _handle_command("surprise")

	except:
		logger.error(sys.exc_info()[1])
		traceback.print_tb(sys.exc_info()[2])
		_publish_event('alert', json.dumps({'message': str(sys.exc_info()[1])}))

	return HttpResponse()#json.dumps({success: True}))

@csrf_exempt
def player_status_and_state(request):	
	
	current_song = PlaylistSong.objects.order_by('id').filter(is_current=True).last()

	if current_song:
		_show_player_status(current_song.song)	
	
	_show_player_state()

	return HttpResponse()

# - HELPERS

def _handle_command(command, albumid=None, songid=None, enqueue=False, play=False, force_play=False):

	global playlist
	global shuffle
	global mute

	logger.debug("Playlist: %s, Shuffle: %s" %(playlist, shuffle))

	next_song = None
	next_playlistsong = None

	response = {}

	if command == "surprise":

		shuffle = True
		playlist = False			
		next_song = _get_next_song()

	elif command == "playlist":

		shuffle = False
		playlist = True
		next_playlistsong = _get_next_playlistsong()

	elif command == "next":
		
		if playlist:
			next_playlistsong = _get_next_playlistsong()
		elif shuffle:
			next_song = _get_next_song()

	elif command == "shuffle":

		shuffle = not shuffle

	elif play:
		
		if songid is not None:
			logger.debug("Fetching song %s" % songid)
			next_song = Song.objects.get(pk=songid)
		elif playlist:
			next_playlistsong = PlaylistSong.objects.filter(is_current=True).first()
		elif shuffle:
			next_song = _get_next_song()

	elif enqueue:

		if albumid is not None:
			
			album = Album.objects.get(pk=albumid)

			for song in album.song_set.all():
				playlistsong = PlaylistSong(song=song)
				playlistsong.save()
				if next_playlistsong is None:
					next_playlistsong = playlistsong

		elif songid is not None:

			song = Song.objects.get(pk=songid)

			playlistsong = PlaylistSong(song=song)
			playlistsong.save()
			if next_playlistsong is None:
				next_playlistsong = playlistsong

		# - 'soft' play to start playback if it isn't already
		force_play = False

	elif command == "pause":
		player_state = PLAYER_STATE_PAUSED
		p.pause()

	elif command == "stop":
		player_state = PLAYER_STATE_STOPPED
		p.stop()

	elif command == "mute":
		mute = not mute
		p.mute()

	if next_song or next_playlistsong:

		if next_song is None and next_playlistsong is not None:
			next_song = next_playlistsong.song

		logger.debug("Playing song %s" % next_song.name)
		played = _play(next_song, force_play)
		
		if played:
			_show_player_status(next_song)
			if next_playlistsong is not None:
				_set_current_song(next_playlistsong)	

	_show_player_state()

	return response	

def _play(song, force_play=False):

	played = p.play(_get_song_filepath(song), "http://%s:%s/player_complete" %(settings.BEATER_HOSTNAME, settings.BEATER_PORT), force_play)
	player_state = PLAYER_STATE_PLAYING
	return played

def _show_player_status(song):

	logger.debug("Showing status..")
	
	status_info = {
		"Title": song.name,
		"Artist": song.album.artist,
		"Album": song.album.name,
		"Year": "?",
		"Track": "?",
		"Genre": "?"
	}	

	_publish_event('player_status', json.dumps(render_to_string('_player_status.html', {'status': status_info})))	

def _show_player_state():
	_publish_event('player_state', json.dumps(
		{
			'shuffle': "on" if shuffle else "off",
			'mute': "on" if mute else "off"
		}
	))

def _get_next_song():

	logger.debug("Fetching next song..")
	next_song = random.choice(Song.objects.all())
	logger.debug("Fetched %s" % next_song.name)
	return next_song

def _get_next_playlistsong():

	logger.debug("Fetching next playlist song..")

	next_playlistsong = None

	if shuffle:
		songs_left = PlaylistSong.objects.filter(played=False)
		if len(songs_left) > 0:
			next_playlistsong = random.choice(songs_left)

	else:
		current_song = PlaylistSong.objects.filter(is_current=True).first()

		if current_song is not None:
			next_playlistsong = PlaylistSong.objects.filter(id__gt=current_song.id).order_by('id').first()
		
		if next_playlistsong is None:
			next_playlistsong = PlaylistSong.objects.all().order_by('id').first()

	if next_playlistsong is not None:
		logger.debug("Fetched %s" % next_playlistsong.song.name)

	return next_playlistsong

def _set_current_song(playlistsong):

	current_playlistsong = PlaylistSong.objects.filter(is_current=True).first()

	if current_playlistsong is not None:
		current_playlistsong.is_current = False
		current_playlistsong.played = True
		current_playlistsong.save()

	playlistsong.is_current = True
	playlistsong.save()
		
def _get_song_filepath(song):

	if beatplayer_music_folder is None:
		raise Exception("The beatplayer-POV music folder is not known")

	return "%s/%s/%s/%s" %(beatplayer_music_folder, song.album.artist, song.album.name, song.name)

'''
def _init_playlist():
	playlist_file = os.path.join(settings.PLAYLIST_WORKING_FOLDER, settings.PLAYLIST_FILENAME)
	logger.debug("opening %s" %playlist_file)
	return open(playlist_file, "wb")
'''
'''
def _write_song_to_playlist(song, playlist):
	full_path = _get_song_filepath(song)
	playlist.write(full_path.encode('utf8'))
'''

def _publish_event(event, payload):

	logger.debug("publishing %s: %s" %(event, payload))
	headers = { "content-type": "application/json" }
	response = requests.post('http://%s:%s/pushevent/%s' %(settings.SWITCHBOARD_SERVER_HOST, settings.SWITCHBOARD_SERVER_PORT, event), headers=headers, data=payload)
	