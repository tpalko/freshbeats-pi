from django.shortcuts import render
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.http import HttpResponse, JsonResponse, QueryDict
from django.db.models import Q
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
import os
import sys
from .models import Album, Artist, Song, AlbumStatus# , Device
import logging
import traceback
import json
import random
import re

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# - PAGES

def home(request):
    '''Home page'''
    # albums = Album.objects.all()
    # alphabet = set([name[0] for name in [re.sub('[\(\)\.]', '', album.artist).lower() for album in albums]])
    # alphabet = sorted(alphabet, cmp=lambda x,y: cmp(x.lower(), y.lower()))
    return render(request, 'home.html', {})


def search(request):

    return render(request, 'search.html', {})


def mobile(request):

    # -- has albumcheckout where return_at is null
    checked_out_albums = Album.objects.filter(Q(albumcheckout__isnull=False) & Q(albumcheckout__return_at__isnull=True))
    checked_out_album_action_bins = {action: [a for a in checked_out_albums if a.action == action] for action in [Album.CHECKIN, Album.REFRESH]}
    checked_out_album_action_sizes = {action: sum([a.total_size if a.action == Album.CHECKIN else (a.total_size - a.old_total_size) for a in checked_out_albums if a.action == action])/(1024*1024) for action in [Album.CHECKIN, Album.REFRESH]}
    checked_out_album_no_action_bins = {action if action else "No Action": [a for a in checked_out_albums if a.action == action] for action in [Album.DONOTHING, None]}
    checked_out_no_action_size = sum([album.total_size for album_list in checked_out_album_no_action_bins.values() for album in album_list])/(1024*1024)

    # -- does not have albumcheckout where return_at is null and action is set
    other_action_albums = Album.objects.filter(~(Q(albumcheckout__isnull=False) & Q(albumcheckout__return_at__isnull=True)) & Q(action__isnull=False))
    other_album_action_bins = {
        action: [a for a in other_action_albums if a.action == action] for action in [Album.REQUESTCHECKOUT, Album.CHECKOUT]}
    other_album_action_sizes = {
        action: sum([a.total_size for a in other_action_albums if a.action == action])/(1024*1024) for action in [Album.REQUESTCHECKOUT, Album.CHECKOUT]}

    return render(request, 'mobile.html', {
        'checked_out_album_action_bins': checked_out_album_action_bins,
        'checked_out_album_action_sizes': checked_out_album_action_sizes,
        'checked_out_album_no_action_bins': checked_out_album_no_action_bins,
        'checked_out_no_action_size': checked_out_no_action_size,
        'other_album_action_bins': other_album_action_bins,
        'other_album_action_sizes': other_album_action_sizes
    })


def devices(request):
    devices = Device.objects.all()
    return render(request, 'devices.html', {'devices': devices})


def manage(request):

    return render(request, 'manage.html', {})


def report(request):
    return render(request, "report.html", {})


def survey(request):

    albums = Album.objects.filter(action=None, albumcheckout__isnull=False, albumcheckout__return_at=None)

    if len(albums) == 0:
        return redirect('beater.views.home')

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


def album_filter(request, filter):

    search = request.GET.get('search')

    albums = []

    if filter == 'checkedout':
        albums = Album.objects.order_by('artist', 'name').filter(albumcheckout__isnull=False, albumcheckout__return_at=None)
    elif filter == AlbumStatus.INCOMPLETE:
        albums = Album.objects.order_by('artist', 'name').filter(albumstatus__status=AlbumStatus.INCOMPLETE)
    elif filter == AlbumStatus.MISLABELED:
        albums = Album.objects.order_by('artist', 'name').filter(albumstatus__status=AlbumStatus.MISLABELED)

    return render(request, '_albums.html', {'albums':albums})

# - AJAX ENDPOINTS


@csrf_exempt
def checkin(request, album_id):

    album = Album.objects.get(pk=album_id)
    album.action = Album.CHECKIN
    album.save()

    return JsonResponse({'album_id': album_id, 'row': render_to_string("_album_row.html", {'album': album})})


@csrf_exempt
def checkout(request, album_id):

    album = Album.objects.get(pk=album_id)
    album.action = Album.REQUESTCHECKOUT
    album.request_priority = 1
    album.save()

    # - is not currently checked out and has an assigned action
    # -- basically is either scheduled to be refreshed or in some to-be-checked-out state
    other_action_albums = Album.objects.filter(~(Q(albumcheckout__isnull=False) & Q(albumcheckout__return_at__isnull=True)) & Q(action__isnull=False))

    # -- bin up actions with sums of album sizes
    # -- limit to this album's action
    other_album_action_sizes = {
        action: sum([a.total_size for a in other_action_albums if a.action == action])/(1024*1024) for action in [Album.REQUESTCHECKOUT]}

    return JsonResponse({
        'album_id': album_id,
        'requestcheckout_size': other_album_action_sizes[Album.REQUESTCHECKOUT],
        'row': render_to_string("_album_row.html", {'album': album})
    })


@csrf_exempt
def cancel(request, album_id):

    album = Album.objects.get(pk=album_id)
    album.action = None
    album.save()

    row_template = "_album_row_checkedin.html"
    state = Album.STATE_CHECKEDIN

    if album.current_albumcheckout():
        row_template = "_album_row_checkedout.html"
        state = Album.STATE_CHECKEDOUT

    return JsonResponse({'state': state, 'album_id': album_id, 'row': render_to_string(row_template, {'album': album})})


@csrf_exempt
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


@csrf_exempt
def album_songs(request, album_id):
    '''Album title: populate 'title' mouseover song list'''
    album = Album.objects.get(pk=album_id)
    return JsonResponse('\n'.join([s.name for s in album.song_set.all()]), safe=False)


@csrf_exempt
def fetch_remainder_albums(request):
    '''Mobile page: populate list of albums to choose from'''
    # -- does not have albumcheckout where return_at is null and action is not set
    remainder_albums = Album.objects.filter(~(Q(albumcheckout__isnull=False) & Q(albumcheckout__return_at__isnull=True)) & Q(action__isnull=True) & Q(sticky=False))

    return JsonResponse({'rows': "".join([render_to_string("_album_row_checkedin.html", {'album': album}) for album in remainder_albums])})


@csrf_exempt
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


@csrf_exempt
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
        _publish_event('alert', json.dumps(response))

    return HttpResponse(json.dumps({'success': True}))

@csrf_exempt
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
            'name_highlight': highlight_replace.sub("<span class='highlight'>%s</span>" % search_string, a.name)
        }) for a in albums]
        songs = Song.objects.filter(name__icontains=search_string)
        songs = [render_to_string('_song.html', {
            'song': s,
            'name_highlight': highlight_replace.sub("<span class='highlight'>%s</span>" % search_string, s.name)}) for s in songs]
        artists = Artist.objects.filter(name__icontains=search_string)
        artists = [render_to_string('_artist.html', {
            'artist': a,
            'name_highlight': highlight_replace.sub("<span class='highlight'>%s</span>" % search_string, a.name),
            'albums': Album.objects.filter(artist_id=a.id)
        }) for a in artists]

    else:

        search_string = "%s%s" % (search_string[0:1].upper(), search_string[1:])
        artists = Artist.objects.filter(name__icontains=search_string)
        artists = [a for a in artists if starts_with_regex.search(a.name)]
        artists = sorted(artists, key=lambda a: a.name.replace(starts_with_regex.search(a.name).group(0), search_string))
        artists = [_get_artist_search_row(a, search_string) for a in artists]

    return JsonResponse({'artists': artists, 'albums': albums, 'songs': songs})


def _get_artist_search_row(artist, search_string=''):
    '''Search page: render artist details'''
    escaped_search_string = re.escape(search_string)
    first_letter_regex = re.compile("\\b%s" % escaped_search_string, re.IGNORECASE)

    return render_to_string('_artist.html', {
        'artist': artist,
        'name_highlight': first_letter_regex.sub("<span class='highlight'>%s</span>" % search_string, artist.name),
        'albums': [render_to_string('_artist_album_row.html', {
            'album': album
        }) for album in Album.objects.filter(artist_id=artist.id)]
    })


@csrf_exempt
@require_POST
def new_artist(request):
    '''Search page: adding new artist'''
    artist_name = request.POST.get('artist_name')

    artist, created = Artist.objects.get_or_create(name=artist_name)

    return JsonResponse({'success': created, 'row': _get_artist_search_row(artist)})


@csrf_exempt
@require_POST
def new_album(request, artist_id):
    '''Search page: adding new album'''
    album_name = request.POST.get('album_name')

    # artist = Artist.objects.get(pk=artist_id)

    album = Album.objects.create(artist_id=artist_id, name=album_name, wanted=True)

    return JsonResponse({'success': True, 'row': render_to_string('_artist_album_row.html', {'album': album}), 'artist_id': artist_id})


@require_GET
def get_album(request, albumid):

    album = Album.objects.get(pk=albumid)

    return render(request, 'album.html', {'album': album, 'songs': album.song_set.all().order_by('name')})


@csrf_exempt
def update_album(request, album_id):

    album_name = QueryDict(request.body).get('album_name')

    album = Album.objects.get(pk=album_id)
    album.name = album_name
    album.save()

    return JsonResponse({'success': True, 'album_name': album_name, 'album_id': album_id})
