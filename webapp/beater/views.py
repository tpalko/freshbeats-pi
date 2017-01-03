from django.shortcuts import render
from django.shortcuts import render_to_response
from django.shortcuts import redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import os
import sys
from models import Album, Artist, AlbumCheckout, Song, AlbumStatus, PlaylistSong
import xmlrpclib
import logging
import traceback
import json
import random
import socket
import requests
import re
from util import capture

sys.path.append(os.path.join(settings.BASE_DIR, "..", "services"))

#logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)
fresh_logger = logging.StreamHandler()

logger.setLevel(logging.DEBUG)
logger.addHandler(fresh_logger)

logger.debug("Setting path for RPi: %s" % settings.BEATPLAYER_SERVER)
p = xmlrpclib.ServerProxy(settings.BEATPLAYER_SERVER)

#logger.debug("Setting callback for RPi")
#p.set_callback("http://%s:%s/player_complete" %(settings.BEATER_HOSTNAME, settings.BEATER_PORT))

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

	#albums = Album.objects.all()

	#alphabet = set([name[0] for name in [re.sub('[\(\)\.]', '', album.artist).lower() for album in albums]])
	#alphabet = sorted(alphabet, cmp=lambda x,y: cmp(x.lower(), y.lower()))

	return render(request, 'home.html', { })

def search(request):

	return render(request, 'search.html', {})

def get_search_results(request):

	search_string = request.GET.get('search')
	highlight_replace = re.compile(re.escape(search_string), re.IGNORECASE)

	albums = Album.objects.filter(name__icontains=search_string)
	albums = [ render_to_string('_album.html', {'album': a, 'name_highlight': highlight_replace.sub("<span class='highlight'>%s</span>" % search_string, a.name)}) for a in albums ]

	artists = Artist.objects.filter(name__icontains=search_string)
	artists = [ render_to_string('_artist.html', {'artist': a, 'name_highlight': highlight_replace.sub("<span class='highlight'>%s</span>" % search_string, a.name)}) for a in artists ]

	songs = Song.objects.filter(name__icontains=search_string)
	songs = [ render_to_string('_song.html', {'song': s, 'name_highlight': highlight_replace.sub("<span class='highlight'>%s</span>" % search_string, s.name)}) for s in songs ]

	return JsonResponse({'artists': artists, 'albums': albums, 'songs': songs})

def playlist(request):
	pass

def mobile(request):
	
	albums = Album.objects.raw("select distinct beater_album.* from beater_album left join beater_albumcheckout on beater_albumcheckout.album_id = beater_album.id where ((beater_albumcheckout.id is not null and beater_albumcheckout.return_at is null) or (beater_album.action is not null))")
	#albums = Album.objects.filter((Q(albumcheckout__isnull=False) & Q(albumcheckout__return_at__isnull=True)) | ~Q(action=None))
	bins = { action: [ a for a in albums if a.action == action ] for action in set([ a.action for a in albums ]) }

	logger.debug(bins)

	return render(request, 'mobile.html', {'bins': bins})

@capture
def select_albums_for_checkout(request):

	try:
		from freshbeats import freshbeats
		f = freshbeats.FreshBeats()
		f.mark_albums()
	except:
		logger.error(sys.exc_info()[1])
		traceback.print_tb(sys.exc_info()[2])

	return JsonResponse({})
	
@capture
def call_report():
	from freshbeats import freshbeats
	f = freshbeats.FreshBeats()
	report_out = f.report() # - logs stuff
	return report_out

def report(request):

	out = call_report()
	logger.info(out)

	return render(request, "report.html", { 'output': out })

def config(request):
	pass

def survey(request):

	albums = Album.objects.filter(action=None, albumcheckout__isnull=False, albumcheckout__return_at=None)

	if len(albums) == 0:
		return redirect('beater.views.home')

	return render(request, 'survey.html', 
		{ 
			'album': random.choice(albums), 
			'album_count': len(albums),
			'rating_choices': Album.ALBUM_RATING_CHOICES, 
			'status_choices': AlbumStatus.ALBUM_STATUS_CHOICES 
		}, 
		context_instance=RequestContext(request))

def albums(request):

	if request.method == "POST":

		action = request.POST.get('action')

		if action == 'clear_rated_albums':

			albums = Album.objects.filter(~Q(rating=Album.UNRATED), action=None, albumcheckout__isnull=False, albumcheckout__return_at=None)

			logger.info("unrated album: %s" % ",".join([ "%s: %s" % (a.name, a.rating) for a in albums ]))

	return JsonResponse({"success": True})

def album(request, albumid):

	album = Album.objects.get(pk=albumid)
	
	return render(request, 'album.html', { 'album': album, 'songs': album.song_set.all().order_by('name') })

# - PARTIALS

def album_filter(request, filter):

	search = request.GET.get('search')

	albums = []

	if filter == 'checkedout':
		albums = Album.objects.order_by('artist', 'name').filter(albumcheckout__isnull=False, albumcheckout__return_at=None)
	elif filter == AlbumStatus.INCOMPLETE:
		albums = Album.objects.order_by('artist', 'name').filter(albumstatus__status=AlbumStatus.INCOMPLETE)
	elif filter == AlbumStatus.MISLABELED:
		albums = Album.objects.order_by('artist', 'name').filter(albumstatus__status=AlbumStatus.MISLABELED)

	return render(request, '_albums.html', { 'albums':albums })

# - AJAX ENDPOINTS

@csrf_exempt
def command(request, type):

	response = { 'result': {}, 'success': False, 'message': "" }

	try:

		if type == "album":
			return _album_command(request)
		elif type == "player":
			return _player_command(request)

		response['success'] = True

	except:
		response['message'] = str(sys.exc_info()[1])
		logger.error(response['message'])
		traceback.print_tb(sys.exc_info()[2])
		_publish_event('alert', json.dumps(response))

	return HttpResponse(json.dumps({'success': True}))

@csrf_exempt
def survey_post(request):

	response = { 'result': {}, 'success': False, 'message': "" }

	try:

		album = Album.objects.get(pk=request.POST.get('albumid'))
		
		album.rating = request.POST.get('rating')
		album.sticky = request.POST.get('sticky', 0)

		if request.POST.get('keep', 0) == 0 and not album.sticky:
			album.action = Album.CHECKIN
		elif album.is_refreshable():
			album.action = Album.REFRESH
		else:
			album.action = Album.DONOTHING

		new_statuses = request.POST.get('statuses', None)

		if new_statuses is not None:
			new_statuses = new_statuses.split(',')
			album.replace_statuses(new_statuses)

		album.save()

		response['success'] = True

	except:
		response['message'] = str(sys.exc_info()[1])
		logger.error(response['message'])
		traceback.print_tb(sys.exc_info()[2])
		_publish_event('alert', json.dumps(response))

	return HttpResponse(json.dumps({'success': True}))

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

	response = { 'result': {}, 'success': False, 'message': "" }

	try:

		logger.debug("Player state: %s" % player_state)

		if player_state == PLAYER_STATE_PLAYING:
			_handle_command("next")

		response['success'] = True

	except:
		response['message'] = str(sys.exc_info()[1])
		logger.error(response['message'])
		traceback.print_tb(sys.exc_info()[2])
		_publish_event('alert', json.dumps(response))

	return HttpResponse(json.dumps({'success': True}))

@csrf_exempt
def player_status_and_state(request):	
	
	response = { 'result': {}, 'success': False, 'message': "" }

	try:

		current_song = PlaylistSong.objects.order_by('id').filter(is_current=True).last()

		if current_song:
			_show_player_status(current_song.song)	
		
		logger.debug("player status and state")
		_show_player_state()

		response['success'] = True

	except:
		response['message'] = str(sys.exc_info()[1])
		logger.error(response['message'])
		traceback.print_tb(sys.exc_info()[2])
		_publish_event('alert', json.dumps(response))

	return HttpResponse(json.dumps({'success': True}))

# - PRIVATE HELPERS

def _album_command(request):

	album = Album.objects.get(pk=request.POST.get('albumid'))
	command = request.POST.get('command')

	if command == "keep":

		album.action = Album.DONOTHING
		album.save()
		response['albumid'] = album.id
		
def player(request, command, albumid=None, songid=None):
	
	problem = None
	player_info = None

	#command = request.POST.get('command', None) # surprise, playlist, next, shuffle, enqueue_album, play/enqueue_song, pause, stop, mute, keep
	#albumid = request.POST.get('albumid', None)
	#songid = request.POST.get('songid', None)

	logger.debug("Got command: %s" % command)

	_handle_command(command, albumid, songid, force_play=True)

def _handle_command(command, albumid=None, songid=None, force_play=False):

	global player_state
	global playlist
	global shuffle
	global mute

	logger.debug("Playlist: %s, Shuffle: %s" %(playlist, shuffle))

	next_song = None
	next_playlistsong = None

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

	elif command == "play":
		
		if songid is not None:
			logger.debug("Fetching song %s" % songid)
			next_song = Song.objects.get(pk=songid)
		elif playlist:
			next_playlistsong = PlaylistSong.objects.filter(is_current=True).first()
		elif shuffle:
			next_song = _get_next_song()

	elif command == "enqueue":

		if albumid is not None:
			
			album = Album.objects.get(pk=albumid)

			for song in album.song_set.all().order_by('name'):
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
		if player_state == PLAYER_STATE_PAUSED:
			player_state = PLAYER_STATE_PLAYING
		else:
			player_state = PLAYER_STATE_PAUSED
		p.pause()

	elif command == "stop":
		if player_state == PLAYER_STATE_STOPPED:
			player_state = PLAYER_STATE_PLAYING
		else:
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

	logger.debug("handled command %s" % command)
	_show_player_state()

def _play(song, force_play=False):

	global player_state

	played = p.play(_get_song_filepath(song), "http://%s:%s/player_complete/" %(settings.BEATER_HOSTNAME, settings.BEATER_PORT), force_play)
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

	beatplayer_music_folder = None
	
	if not beatplayer_music_folder:
		try:
			logger.debug("Calling to get music folder..")
			beatplayer_music_folder = p.get_music_folder()
			logger.debug("Music folder found: %s" % beatplayer_music_folder)
		except:
			logger.error("Music folder NOT found")

	if beatplayer_music_folder is None:
		raise Exception("beatplayer is not responding")

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
	
