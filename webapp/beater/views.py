from django.shortcuts import render
from django.shortcuts import render_to_response
from django.shortcuts import redirect
from django.template import RequestContext
from django.http import HttpResponse
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import os
import sys
from models import Album, AlbumCheckout, Song, AlbumStatus
import xmlrpclib
import logging
import traceback
import json
import random

#logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger('beater')
fresh_logger = logging.StreamHandler()

logger.setLevel(logging.DEBUG)
logger.addHandler(fresh_logger)

p = xmlrpclib.ServerProxy(settings.BEATPLAYER_SERVER)
playlist = None

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

def album_filter(request, filter):

	search = request.GET.get('search')

	logger.debug(search)
	
	albums = []

	if filter == 'all':
		albums = Album.objects.order_by('artist', 'name').all()
	elif filter == 'checkedout':
		albums = Album.objects.order_by('artist', 'name').filter(albumcheckout__isnull=False, albumcheckout__return_at=None)
	elif filter == AlbumStatus.INCOMPLETE:
		albums = Album.objects.order_by('artist', 'name').filter(albumstatus__status=AlbumStatus.INCOMPLETE)
	elif filter == AlbumStatus.MISLABELED:
		albums = Album.objects.order_by('artist', 'name').filter(albumstatus__status=AlbumStatus.MISLABELED)

	return render_to_response('_albums.html', { 'albums':albums }, context_instance=RequestContext(request))

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

def home(request):

	return render_to_response('home.html', { }, context_instance=RequestContext(request))

def album(request, albumid):

	album = Album.objects.get(pk=albumid)

	return render_to_response('album.html', { 'album': album, 'songs': album.song_set.all() }, context_instance=RequestContext(request))

#@require_http_methods(["POST"])

@csrf_exempt
def player_command(request):

	response = {}
	
	try:

		problem = None
		player_info = None

		command = request.POST['command']

		shuffle = True if 'shuffle' in request.POST else False

		if command == "keep":

			album = Album.objects.get(pk=request.POST['albumid'])
			album.action = Album.DONOTHING
			album.save()
			response['albumid'] = album.id;

		# - caution, this assumes the player command text is the same that being issued by the client
		elif command == "pause":

			p.pause()

		elif command == "stop":

			p.stop()

		elif command == "mute":

			p.mute()

		elif command == "shuffle":
			
			albums = Album.objects.all()
			playlist = _init_playlist()
			
			for album in albums:
				for song in album.song_set.all():
					_write_song_to_playlist(song, playlist)

			playlist.close()
						
			p.play({'shuffle': True})		

		elif command == "album":

			# /mnt/music/Faith No More/Album of the Year/Faith No More_Album of the Year_01_Collision.mp3

			album = Album.objects.get(pk=request.POST['albumid'])
			playlist = _init_playlist()

			logging.debug("playing album %s" %(album.name))
			
			for song in album.song_set.all():
				_write_song_to_playlist(song, playlist)

			playlist.close()

			p.play({'shuffle': shuffle})

		elif command == "song":

			song = Song.objects.get(pk=request.POST['songid'])
			playlist = _init_playlist()

			_write_song_to_playlist(song, playlist)

			playlist.close()

			p.play({'shuffle': shuffle})

		elif command == "next":
			
			p.next()

	except:
		problem = sys.exc_info()[2]
		logging.error(sys.exc_info())
		traceback.print_tb(sys.exc_info()[2])

	return HttpResponse(json.dumps(response))

def _init_playlist():
	return open(os.path.join(settings.PLAYLIST_WORKING_FOLDER, settings.PLAYLIST_FILENAME), "wb")

def _write_song_to_playlist(song, playlist):
	full_path = "%s/%s/%s/%s\r\n" %(settings.MUSIC_MOUNT, song.album.artist, song.album.name, song.name)
	playlist.write(full_path.encode('utf8'))
	
@csrf_exempt
def player_status(request):

	player_status = p.get_player_info()

	return render_to_response('_player_status.html', {'status': player_status}, context_instance=RequestContext(request))
