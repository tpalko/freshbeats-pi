import json
import logging
import os
import random
import re
import sys
import traceback
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, QueryDict
from django.shortcuts import render
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
#from django.views.decorators.csrf import csrf_exempt
from beater.forms import PlaylistForm, DeviceForm, MobileForm
from beater.models import Album, Artist, Song, AlbumStatus, PlaylistSong, Playlist, Device, Mobile, AlbumCheckout
from beater.monitoring.health import BeatplayerHealth
from beater.common.util import get_session_value, set_session_value
from beater.switchboard.switchboard import SwitchboardClient

logger = logging.getLogger()

# - PAGES

def home(request):
    '''Home page'''
    # albums = Album.objects.all()
    # alphabet = set([name[0] for name in [re.sub('[\(\)\.]', '', album.artist).lower() for album in albums]])
    # alphabet = sorted(alphabet, cmp=lambda x,y: cmp(x.lower(), y.lower()))
    return render(request, 'home.html', {})

def _standard_response(success=True, message='', body='', object={}):
    return JsonResponse({
        'success': success,
        'message': message,
        'body': body,
        'object': object
    })

def _render_playlists(selected_playlist_id):
    playlists = Playlist.objects.all()    
    return render_to_string('_playlists.html', { 'playlists': playlists, 'selected_playlist_id': selected_playlist_id })

def playlists(request):
    '''
    Render playlists page 
    '''
    form = PlaylistForm()
    return render(request, 'playlists.html', { 'playlist_form': form })

def get_playlists(request):
    '''
    Fetch playlist <select>
    '''    
    playlist_id = get_session_value(request, 'playlist_id')
    return _standard_response(body=_render_playlists(selected_playlist_id=playlist_id))

def get_playlistsongs(request, playlist_id):
    '''
    Get playlistsongs for a playlist
    '''
    playlist = Playlist.objects.get(pk=playlist_id)
    playlistsongs = PlaylistSong.objects.filter(playlist_id=playlist_id).order_by("queue_number")
    return JsonResponse({'body': render_to_string('_playlistsongs.html', { 'playlistsongs': playlistsongs }), 'object': {'playlist_id': playlist_id}})

def playlist(request):
    '''
    Create a new playlist 
    '''
    returnval = {'message': '', 'success': False, 'body': None, 'object': {}}
    if request.method == 'POST':
        form = PlaylistForm(request.POST)
        if form.is_valid():
            playlist = Playlist.objects.create(name=form.cleaned_data['name'])
            # -- only if the session doesn't already have one, this becomes the current 
            set_session_value(request, 'playlist_id', playlist.id, force=False)
            playlist_id = get_session_value(request, 'playlist_id')
            
            returnval['body'] = _render_playlists(selected_playlist_id=playlist_id)
            returnval['success'] = True 
        else:
            returnval['message'] = form.errors
    return JsonResponse(returnval)

def playlist_sort(request):
    logger.info(dir(request))
    logger.info(request.body)
    logger.info(request.is_ajax())
    return JsonResponse({ 'success': True })


def search(request):
    return render(request, 'search.html', {})


def mobile(request):
    
    mobile_id = get_session_value(request, 'mobile_id')
    
    checked_out_album_next_state_bins = {}
    checked_out_album_next_state_sizes = {}
    checked_out_no_state_albums = []
    checked_out_no_state_albums_size = 0
    mobile_state_bins = {}
    mobile_state_bin_sizes = {}
    checked_out_album_next_state_bin_sizes = {}
    
    if mobile_id:
        
        mobile = Mobile.objects.get(pk=mobile_id)
        state_bins = mobile.state_bins()
                    
        # mobile_checkouts = mobile.albumcheckout_set.filter(Q(state=AlbumCheckout.CHECKEDOUT))
        
        checked_out_album_next_state_bins = {next_state: [ ac.album for ac in state_bins[AlbumCheckout.CHECKEDOUT] if ac.next_state == next_state ] for next_state in [AlbumCheckout.REFRESH, AlbumCheckout.CHECKEDIN]}
        checked_out_album_next_state_bin_sizes = {next_state: sum([(a.total_size - a.old_total_size) if next_state == AlbumCheckout.REFRESH else a.total_size for a in checked_out_album_next_state_bins[next_state]]) for next_state in checked_out_album_next_state_bins.keys() }
        # -- bin by state: sum total_size if checkin, otherwise size delta 
        # checked_out_album_next_state_sizes = {state: sum([ac.album.total_size if ac.next_state == AlbumCheckout.CHECKEDIN else (ac.album.total_size - ac.album.old_total_size) for ac in mobile_checkouts if ac.state == state])/(1024*1024) for state in [AlbumCheckout.REFRESH, AlbumCheckout.CHECKEDIN]}
        
        checked_out_no_state_albums = [ {**ac.album.__dict__, 'mobile_state': AlbumCheckout.CHECKEDOUT} for ac in state_bins[AlbumCheckout.CHECKEDOUT] if ac.next_state is None ]
        # for album in checked_out_no_state_albums:
        #     album.mobile_state = AlbumCheckout.CHECKEDOUT 
        checked_out_no_state_albums_size = sum([ album['total_size'] for album in checked_out_no_state_albums ])/(1024*1024)
        
        # mobile_state = mobile.albumcheckout_set.filter(Q(state=AlbumCheckout.REQUESTED) | Q(state=AlbumCheckout.VALIDATED))
        mobile_state_bins = { state: [ac.album for ac in state_bins[state]] for state in [AlbumCheckout.REQUESTED, AlbumCheckout.VALIDATED] }
        mobile_state_bin_sizes = { state: sum([a.total_size for a in mobile_state_bins[state]])/(1024*1024) for state in mobile_state_bins.keys() }
        
        # -- does not have albumcheckout where return_at is null and action is set
        # other_action_albums = Album.objects.filter(Q(albumcheckout__mobile=mobile_id) & ~(Q(albumcheckout__isnull=False) & Q(albumcheckout__return_at__isnull=True)) & Q(action__isnull=False))
        # other_album_action_bins = {
        #     action: [a for a in other_action_albums if a.action == action] for action in [Album.REQUESTCHECKOUT, Album.CHECKOUT]}
        # other_album_action_sizes = {
        #     action: sum([a.total_size for a in other_action_albums if a.action == action])/(1024*1024) for action in [Album.REQUESTCHECKOUT, Album.CHECKOUT]}
    
    return render(request, 'mobile.html', {
        'mobile_id': mobile_id,
        'checked_out_album_next_state_bins': checked_out_album_next_state_bins,
        'checked_out_album_next_state_bin_sizes': checked_out_album_next_state_bin_sizes,
        'checked_out_no_state_albums': checked_out_no_state_albums,
        'checked_out_no_state_albums_size': checked_out_no_state_albums_size,
        'mobile_state_bins': mobile_state_bins,
        'mobile_state_bin_sizes': mobile_state_bin_sizes
    })

def mobile_delete(request, mobile_id):
    mobile = Mobile.objects.get(pk=mobile_id)
    mobile.delete()
    return redirect('devices')

def mobile_edit(request, mobile_id):
    mobile = Mobile.objects.get(pk=mobile_id)
    if request.method == "POST":
        form = MobileForm(request.POST, instance=mobile)
        if form.is_valid():
            form.save()
        return redirect('devices')
    else:
        form = MobileForm(instance=mobile)
    
    return render(request, 'mobile_form.html', {'mobile': mobile, 'form': form})

def mobile_new(request):
    
    form = MobileForm()
    
    if request.method == "POST":
        form = MobileForm(request.POST)
        if form.is_valid():
            save_id = form.save()
            logger.debug("save ID: %s" % save_id)
            return redirect('devices')
    
    return render(request, 'mobile_form.html', {'form': form})
    
def device_delete(request, device_id):
    device = Device.objects.get(pk=device_id)
    device.delete()
    return redirect('devices')

def device_edit(request, device_id):
    device = Device.objects.get(pk=device_id)
    if request.method == "POST":
        beatplayer = BeatplayerHealth.getInstance(agent_base_url=device.agent_base_url)
        with beatplayer.device(logger=logger) as lockdevice:
            form = DeviceForm(request.POST, instance=lockdevice)
            if form.is_valid():
                form.save()
        return redirect('devices')
    else:
        form = DeviceForm(instance=device)
    
    return render(request, 'device_form.html', {'device': device, 'form': form})

def device_new(request):
    
    form = DeviceForm()
    
    if request.method == "POST":
        form = DeviceForm(request.POST)
        if form.is_valid():
            save_id = form.save()
            logger.debug("save ID: %s" % save_id)
            return redirect('devices')
    
    return render(request, 'device_form.html', {'form': form})
    
def devices(request):
    devices = Device.objects.all()
    mobiles = Mobile.objects.all()
    return render(request, 'devices.html', {'devices': devices, 'mobiles': mobiles})


def manage(request):

    return render(request, 'manage.html', {})


def report(request):
    return render(request, "report.html", {})


def survey(request):
        
    mobile_id = get_session_value(request, 'mobile_id')
    albums = []
    
    if mobile_id:            
        mobile = Mobile.objects.get(pk=mobile_id)
        albums = mobile.albumcheckout_set.filter(state=AlbumCheckout.CHECKEDOUT, next_state__isnull=True)

    if len(albums) == 0:
        return redirect('home')

    return render(request, 'survey.html', {
        'album': random.choice(albums),
        'album_count': len(albums),
        'rating_choices': Album.ALBUM_RATING_CHOICES,
        'status_choices': AlbumStatus.ALBUM_STATUS_CHOICES
    })


def albums(request):

    if request.method == "POST":

        action = request.POST.get('action')

        # -- from the survey page
        if action == 'clear_rated_albums':

            albums = Album.objects.filter(~Q(rating=Album.UNRATED), action=None, albumcheckout__isnull=False, albumcheckout__return_at=None)

            logger.info("unrated album: %s", ",".join(["%s: %s" % (a.name, a.rating) for a in albums]))

    return JsonResponse({"success": True})


# - PARTIALS


# def album_filter(request, filter):
# 
#     search = request.GET.get('search')
# 
#     albums = []
# 
#     if filter == 'checkedout':
#         albums = Album.objects.order_by('artist', 'name').filter(albumcheckout__isnull=False, albumcheckout__return_at=None)
#     elif filter == AlbumStatus.INCOMPLETE:
#         albums = Album.objects.order_by('artist', 'name').filter(albumstatus__status=AlbumStatus.INCOMPLETE)
#     elif filter == AlbumStatus.MISLABELED:
#         albums = Album.objects.order_by('artist', 'name').filter(albumstatus__status=AlbumStatus.MISLABELED)
# 
#     return render(request, '_albums.html', {'albums':albums})

# - AJAX ENDPOINTS


def checkin(request, album_id):

    album = Album.objects.get(pk=album_id)
    mobile_id = get_session_value(request, 'mobile_id')
    
    album_checkout = album.current_albumcheckout(mobile_id)
    if album_checkout:
        album_checkout.next_state = AlbumCheckout.CHECKEDIN 
        album_checkout.save()

    return JsonResponse({'album_id': album_id, 'row': render_to_string("_album_row.html", {'album': album})})


def checkout(request, album_id):
    
    album = Album.objects.get(pk=album_id)
    mobile_id = get_session_value(request, 'mobile_id')
    mobile = Mobile.objects.get(pk=mobile_id)
    
    album_checkout = album.current_albumcheckout(mobile_id)
    if album_checkout:
        logger.warning(f'Cannot request checkout for {album.name} as it already has an active (not checked-in) checkout: {album_checkout.id} in {album_checkout.state} state.')
    else:
        AlbumCheckout.objects.create(album=album, mobile=mobile, state=AlbumCheckout.REQUESTED)
        
    state_bins = mobile.state_bins()
    mobile_state_bins = { state: [ac.album for ac in state_bins[state]] for state in [AlbumCheckout.REQUESTED, AlbumCheckout.VALIDATED] }
    mobile_state_bin_sizes = { state: sum([a.total_size for a in mobile_state_bins[state]])/(1024*1024) for state in mobile_state_bins.keys() }
    requestcheckout_size = mobile_state_bin_sizes[AlbumCheckout.REQUESTED]
    
    # - is not currently checked out and has an assigned action
    # -- basically is either scheduled to be refreshed or in some to-be-checked-out state
    # other_action_albums = Album.objects.filter(~(Q(albumcheckout__isnull=False) & Q(albumcheckout__return_at__isnull=True)) & Q(action__isnull=False))

    # -- bin up actions with sums of album sizes
    # -- limit to this album's action
    # other_album_action_sizes = {
    #     action: sum([a.total_size for a in other_action_albums if a.action == action])/(1024*1024) for action in [Album.REQUESTCHECKOUT]}

    return JsonResponse({
        'album_id': album_id,
        'requestcheckout_size': requestcheckout_size,
        'row': render_to_string("_album_row.html", {'album': album})
    })


def cancel(request, album_id):

    album = Album.objects.get(pk=album_id)
    mobile_id = get_session_value(request, 'mobile_id')
    
    '''
    2. albumcheckout.state = requested, next_state = None 
    3. albumcheckout.state = validated, next_state = checkedout  
    4. albumcheckout.state = checkedout, next_state = None,         checkedout_at = now 
    5. albumcheckout.state = checkedout, next_state = refresh,      checkedout_at = now 
    6. albumcheckout.state = checkedout, next_state = None,         checkedout_at = now 
    7. albumcheckout.state = checkedout, next_state = checkedin,    checkedout_at = now 
    8. albumcheckout.state = checkedin,  next_state = None,         checkedout_at = now, return_at = now 
    '''
    
    # -- state is either in our out 
    # -- we just need to know in what box to put the cancelled album in the UI 
    # -- default is 'remainder'
    state = AlbumCheckout.CHECKEDIN
    checkout = album.current_albumcheckout(mobile_id)
    
    if checkout:
        if checkout.state in [AlbumCheckout.REQUESTED, AlbumCheckout.VALIDATED]:
            checkout.delete()
        else:
            state = checkout.state
            checkout.next_state = None 
            checkout.save()
    
    album.mobile_state = state 

    return JsonResponse({'state': state, 'album_id': album_id, 'row': render_to_string("_album_row_state.html", {'album': album})})


def album_flag(request, album_id, album_status):

    album = Album.objects.get(pk=album_id)
    status, created = AlbumStatus.objects.get_or_create(album_id=album_id, status=album_status)

    row = None

    if not created:
        status.delete()

    #album_path = os.path.join(settings.MUSIC_PATH, album.artist.name.encode('utf-8'), album.name.encode('utf-8'))
    #, 'album_path': album_path})

    row = _get_album_manage_row(album)

    return JsonResponse({'album_id': album_id, 'row': row})


def _get_album_manage_row(album):

    album_statuses = album.albumstatus_set.all()

    return render_to_string("_album_row_manage.html", {
        'status_choices': AlbumStatus.ALBUM_STATUS_CHOICES,
        'album': album,
        'artist': album.artist,
        'album_statuses': album_statuses
    })


def album_art(request, album_id):

    album = Album.objects.get(pk=album_id)
    # album_path = os.path.join(settings.MUSIC_PATH, album.artist.name.encode('utf-8'), album.name.encode('utf-8'))


def album_songs(request, album_id):
    '''Album title: populate 'title' mouseover song list'''
    album = Album.objects.get(pk=album_id)
    return JsonResponse('\n'.join([s.name for s in album.song_set.all()]), safe=False)


def fetch_remainder_albums(request):
    '''Mobile page: populate list of albums to choose from'''
    
    remainder_albums = []
    mobile_id = get_session_value(request, 'mobile_id')
    
    if mobile_id:
        mobile = Mobile.objects.get(pk=mobile_id)
        remainder_albums = Album.objects.raw('select distinct a.* \
            from beater_album a \
            left outer join beater_albumcheckout ac on ac.album_id = a.id \
            where a.deleted = 0 \
            and (\
                ac.id is null \
                or a.id not in (\
                    select u1.album_id \
                    from beater_albumcheckout u1 \
                    where u1.state in (%s) \
                    and u1.mobile_id = %s\
                )\
            )', (AlbumCheckout.REQUESTED, mobile.id,))
        # -- albums 
        # -- no albumcheckout 
        # -- OR 
        # -- albumcheckout rules (or'd)
        # -- 1. not our mobile
        # -- 2. is our mobile and is checked-in 
        # remainder_albums = Album.objects.filter(
        #     Q(albumcheckout__isnull=True) 
        #     | (
        #         Q(albumcheckout__state=AlbumCheckout.CHECKEDIN) 
        #         & (
        #             ~Q(albumcheckout__mobile=mobile) 
        #             | (
        #                 Q(albumcheckout__mobile=mobile) 
        #                 & ~Q(albumcheckout__state__in=[AlbumCheckout.REQUESTED, AlbumCheckout.VALIDATED])
        #             )
        #         )
        #     )
        # ).distinct()
                # | ~Q(albumcheckout__mobile=mobile))
        # ~(Q(albumcheckout__mobile=mobile_id) & Q(albumcheckout__isnull=False) & Q(albumcheckout__return_at__isnull=True)) & Q(action__isnull=True) & Q(sticky=False))

    return JsonResponse({'rows': "".join([render_to_string("_album_row_checkedin.html", {'album': album}) for album in remainder_albums])})

def fetch_manage_albums(request):
    '''Manage page: populate list'''
    albums = Album.objects.all()

    '''
    'album_path': os.path.join(
                            settings.MEDIA_ROOT,
                            album.artist.name.encode('utf-8'),
                            album.name.encode('utf-8')
                        )
    '''

    return JsonResponse({
        'rows': "".join([_get_album_manage_row(album) for album in albums])
    })


def survey_post(request):
    '''Survey page: album post'''
    response = {'result': {}, 'success': False, 'message': ""}

    try:

        album = Album.objects.get(pk=request.POST.get('albumid'))

        album.rating = request.POST.get('rating')
        album.sticky = request.POST.get('sticky', 0) == 1

        keep = request.POST.get('keep', 0) == 1

        if not keep and not album.sticky:
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
        SwitchboardClient.getInstance().publish_event('alert', json.dumps(response))

    return HttpResponse(json.dumps({'success': True}))

def get_search_results(request):
    '''Search page: handle search'''
    record_shop_mode = bool(int(request.POST.get('record_shop_mode')))
    search_string = request.POST.get('search')
    escaped_search_string = re.escape(search_string)
    highlight_replace = re.compile(escaped_search_string, re.IGNORECASE)
    starts_with_regex = re.compile("^the %s|^%s|^\w+\s%s" % (escaped_search_string, escaped_search_string, escaped_search_string), re.IGNORECASE)

    albums = []
    artists = []
    songs = []

    logger.info("record_shop_mode: {}, search_string: {}".format(record_shop_mode, search_string))

    if not record_shop_mode:

        albums = Album.objects.filter(name__icontains=search_string)
        albums = [render_to_string('_album.html', {
            'album': a,
            'name_highlight': highlight_replace.sub(f'<span class="highlight">{search_string}</span>', a.name)
        }) for a in albums]

        songs = Song.objects.filter(name__icontains=search_string)
        songs = [render_to_string('_song.html', {
            'song': s,
            'name_highlight': highlight_replace.sub(f'<span class="highlight">{search_string}</span>', s.name)}) for s in songs]
        
        artists = Artist.objects.filter(name__icontains=search_string)
        artists = [render_to_string('_artist.html', {
            'artist': a,
            'name_highlight': highlight_replace.sub(f'<span class="highlight">{search_string}</span>', a.name),
            'albums': Album.objects.filter(artist_id=a.id)
        }) for a in artists]

    else:

        search_string = "%s%s" % (search_string[0:1].upper(), search_string[1:])
        artists = Artist.objects.filter(name__icontains=search_string)
        artists = [a for a in artists if starts_with_regex.search(a.name)]
        artists = sorted(artists, key=lambda a: a.name.replace(starts_with_regex.search(a.name).group(0), search_string))
        artists = [_get_artist_search_row(a, search_string) for a in artists]

    return JsonResponse({'artists': "".join(artists), 'albums': "".join(albums), 'songs': "".join(songs)})


def _get_artist_search_row(artist, search_string=''):
    '''Search page: render artist details'''
    escaped_search_string = re.escape(search_string)
    first_letter_regex = re.compile("\\b%s" % escaped_search_string, re.IGNORECASE)

    return render_to_string('_artist_recordshop.html', {
        'artist': artist,
        'name_highlight': first_letter_regex.sub("<span class='highlight'>%s</span>" % search_string, artist.name)
    })


@require_POST
def new_artist(request):
    '''Search page: adding new artist'''
    artist_name = request.POST.get('artist_name')

    artist, created = Artist.objects.get_or_create(name=artist_name)

    return JsonResponse({'success': created, 'row': _get_artist_search_row(artist)})


@require_POST
def new_album(request, artist_id):
    '''Search page: adding new album'''
    
    album_name = request.POST.get('album_name')

    artist = Artist.objects.get(pk=artist_id)
    logger.debug(f'creating album with artist {artist_id}, name {album_name}, artist {artist}')

    
    album = Album(artist=artist, name=album_name)
    AlbumStatus(album=album, status=AlbumStatus.WANTED)
    album.save()

    return JsonResponse({'success': True, 'row': render_to_string('_artist_album_row.html', {'album': album}), 'artist_id': artist_id})


@require_GET
def get_album(request, albumid):

    album = Album.objects.get(pk=albumid)

    return render(request, 'album.html', {'album': album, 'songs': album.song_set.all().order_by('name')})


def update_album(request, album_id):

    album_name = QueryDict(request.body).get('album_name')

    album = Album.objects.get(pk=album_id)
    album.name = album_name
    album.save()

    return JsonResponse({'success': True, 'album_name': album_name, 'album_id': album_id})
