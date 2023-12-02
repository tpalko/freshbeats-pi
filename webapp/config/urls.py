"""beater URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""

from django.urls import re_path 
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings

from beater import views
from beater.beatplayer import handlers as beatplayer_handlers
from beater.freshbeats import freshbeats_client
from beater.monitoring import monitor_handlers



urlpatterns = [
    re_path(r'^$', views.home, name='home'),
    re_path(r'^search/$', views.search, name='search'),
    re_path(r'^devices/(?P<device_id>[0-9]+)/delete$', views.device_delete, name='device_delete'),
    re_path(r'^devices/(?P<device_id>[0-9]+)/$', views.device_edit, name='device_edit'),
    re_path(r'^mobile_form/(?P<mobile_id>[0-9]+)/delete$', views.mobile_delete, name='mobile_delete'),
    re_path(r'^mobile_form/(?P<mobile_id>[0-9]+)/$', views.mobile_edit, name='mobile_edit'),
    
    re_path(r'^devices/$', views.devices, name='devices'),
    re_path(r'^mobile_form/$', views.mobile_new, name='mobile_new'),
    re_path(r'^device/$', views.device_new, name='device_new'),
    re_path(r'^mobile/$', views.mobile, name='mobile'),
    re_path(r'^manage/$', views.manage, name='manage'),
    re_path(r'^report/$', views.report, name='report'),
    re_path(r'^survey/$', views.survey, name='survey'),

    re_path(r'^playlists/$', views.playlists, name='playlists'),
    re_path(r'^playlist/$', views.playlist, name='playlist'),
    re_path(r'^playlist/sort$', views.playlist_sort, name='playlist_sort'),
    
    re_path(r'^partials/playlists/selected/(?P<selected>[0-9]+)$', views.get_playlists, name='get_playlists'),
    re_path(r'^partials/playlists/$', views.get_playlists, name='get_playlists'),
    re_path(r'^partials/playlistsongs/(?P<playlist_id>[0-9]+)/$', views.get_playlistsongs, name='get_playlistsongs'),

    re_path(r'^player/(?P<command>[a-z\_A-Z]+)/$', beatplayer_handlers.player, name='player'),
    # url(r'^player/(?P<command>[a-zA-Z]+)/album/(?P<albumid>[0-9]+)/$', beatplayer_handlers.player, name='album_command'),
    # url(r'^player/(?P<command>[a-zA-Z]+)/song/(?P<songid>[0-9]+)/$', beatplayer_handlers.player, name='song_command'),
    # url(r'^player/(?P<command>[a-zA-Z]+)/$', beatplayer_handlers.player, name='player'),
    
    re_path(r'^device_select/$', beatplayer_handlers.device_select, name='device_select'),
    re_path(r'^mobile_select/$', beatplayer_handlers.mobile_select, name='mobile_select'),
    re_path(r'^playlist_select/$', beatplayer_handlers.playlist_select, name='playlist_select'),
    re_path(r'^player_complete/$', beatplayer_handlers.player_complete, name='player_complete'),
    
    re_path(r'^apply_plan/$', freshbeats_client.apply_plan, name='apply_plan'),
    re_path(r'^validate_plan/$', freshbeats_client.validate_plan, name='validate_plan'),
    re_path(r'^plan_report/$', freshbeats_client.plan_report, name='plan_report'),
    re_path(r'^update_db/$', freshbeats_client.update_db, name='update_db'),

    re_path(r'^register_client/$', monitor_handlers.register_client, name='register_client'),
    # re_path(r'^devices/health_loop/$', monitor_handlers.device_health_loop, name='device_health_loop'),
    re_path(r'^device_health_report/$', monitor_handlers.device_health_report, name='device_health_report'),
    re_path(r'^log_client_presence/$', monitor_handlers.log_client_presence, name='log_client_presence'),    
    re_path(r'^player_status_and_state/$', monitor_handlers.player_status_and_state, name='player_status_and_state'),

    re_path(r'^albums/$', views.albums, name='albums'),

    #url(r'^album_filter/filter/(?P<filter>[a-z0-9]+)/$', views.album_filter),
    #url(r'^album_filter/letter/(?P<letter>[a-z0-9])/$', views.album_letter),

    re_path(r'^album/(?P<album_id>[0-9]+)/checkin/$', views.checkin, name='album_checkin'),
    re_path(r'^album/(?P<album_id>[0-9]+)/checkout/$', views.checkout, name='album_checkout'),
    re_path(r'^album/(?P<album_id>[0-9]+)/cancel/$', views.cancel, name='album_cancel'),
    re_path(r'^album/(?P<album_id>[0-9]+)/flag/(?P<album_status>[a-z\s]+)/$', views.album_flag, name='album_flag'),
    re_path(r'^album/(?P<album_id>[0-9]+)/songs/$', views.album_songs, name='album_songs'),
    re_path(r'^album/(?P<album_id>[0-9]+)/$', views.update_album, name="update_album"),
    re_path(r'^artist/(?P<artist_id>[0-9]+)/album/$', views.new_album, name="new_album"),
    re_path(r'^artist/$', views.new_artist, name="new_artist"),
    re_path(r'^album/(?P<albumid>[0-9]+)/$', views.get_album, name='get_album'),
    re_path(r'^remainder_albums/$', views.fetch_remainder_albums, name='fetch_remainder_albums'),
    re_path(r'^fetch_manage_albums/$', views.fetch_manage_albums, name='fetch_manage_albums'),
    re_path(r'^survey_post/$', views.survey_post, name='survey_post'),
    re_path(r'^get_search_results/$', views.get_search_results, name='get_search_results'),

    re_path(r'^admin/', admin.site.urls),    
    #static(r'^%s/(?P<album_id>[0-9]+)/$' % settings.MEDIA_URL, views.album_art, document_root=settings.MEDIA_ROOT)
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# -- adding static(STATIC_URL) enables app static files with gunicorn, but debug_toolbar static files are not found 

# -- runserver finds app and debug_toolbar static files without the static(STATIC_URL), debug True or False and no DIRS or FINDERS 
# -- gunicorn finds no static files in this state 
# -- adding static(STATIC_URL) allows gunicorn to find app static files, but not debug_toolbar 

# if settings.DEBUG:
#     print("IS DEBUG -- loading debug toolbar")
#     import debug_toolbar 
#     urlpatterns = [
#         re_path(r'^__debug__/', include(debug_toolbar.urls)),
#     ] + urlpatterns
