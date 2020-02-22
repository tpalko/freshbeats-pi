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
from django.conf.urls import url, include
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings
from beater import views
from beater import beatplayer
from beater import freshbeats_client
 
urlpatterns = [
    url(r'^$', views.home, name='home'),
    url(r'^search/$', views.search, name='search'),
    url(r'^mobile/$', views.mobile, name='mobile'),
    url(r'^devices/$', views.devices, name='devices'),
    url(r'^manage/$', views.manage, name='manage'),
    url(r'^report/$', views.report, name='report'),
    url(r'^survey/$', views.survey, name='survey'),

    url(r'^command/(?P<type>[a-zA-Z]+)/$', beatplayer.command, name='command'),
    # url(r'^player/(?P<command>[a-zA-Z]+)/album/(?P<albumid>[0-9]+)/$', beatplayer.player, name='album_command'),
    # url(r'^player/(?P<command>[a-zA-Z]+)/song/(?P<songid>[0-9]+)/$', beatplayer.player, name='song_command'),
    # url(r'^player/(?P<command>[a-zA-Z]+)/$', beatplayer.player, name='player'),
    url(r'^player_complete/$', beatplayer.player_complete, name='player_complete'),
    url(r'^health_response/$', beatplayer.health_response, name='health_response'),
    url(r'^beatplayer_status/$', beatplayer.beatplayer_status, name='beatplayer_status'),
    url(r'^player_status_and_state/$', beatplayer.player_status_and_state, name='player_status_and_state'),
    url(r'^apply_plan/$', freshbeats_client.apply_plan, name='apply_plan'),
    url(r'^validate_plan/$', freshbeats_client.validate_plan, name='validate_plan'),
    url(r'^plan_report/$', freshbeats_client.plan_report, name='plan_report'),
    url(r'^update_db/$', freshbeats_client.update_db, name='update_db'),

    url(r'^albums/$', views.albums, name='albums'),

    #url(r'^album_filter/filter/(?P<filter>[a-z0-9]+)/$', views.album_filter),
    #url(r'^album_filter/letter/(?P<letter>[a-z0-9])/$', views.album_letter),

    url(r'^album/(?P<album_id>[0-9]+)/checkin/$', views.checkin, name='album_checkin'),
    url(r'^album/(?P<album_id>[0-9]+)/checkout/$', views.checkout, name='album_checkout'),
    url(r'^album/(?P<album_id>[0-9]+)/cancel/$', views.cancel, name='album_cancel'),
    url(r'^album/(?P<album_id>[0-9]+)/flag/(?P<album_status>[a-z\s]+)/$', views.album_flag, name='album_flag'),
    url(r'^album/(?P<album_id>[0-9]+)/songs/$', views.album_songs, name='album_songs'),
    url(r'^album/(?P<album_id>[0-9]+)/$', views.update_album, name="update_album"),
    url(r'^artist/(?P<artist_id>[0-9]+)/album/$', views.new_album, name="new_album"),
    url(r'^artist/$', views.new_artist, name="new_artist"),
    url(r'^album/(?P<albumid>[0-9]+)/$', views.get_album, name='get_album'),
    url(r'^remainder_albums/$', views.fetch_remainder_albums, name='fetch_remainder_albums'),
    url(r'^fetch_manage_albums/$', views.fetch_manage_albums, name='fetch_manage_albums'),
    url(r'^survey_post/$', views.survey_post, name='survey_post'),
    url(r'^get_search_results/$', views.get_search_results, name='get_search_results'),

    url(r'^admin/', admin.site.urls),    
    #static(r'^%s/(?P<album_id>[0-9]+)/$' % settings.MEDIA_URL, views.album_art, document_root=settings.MEDIA_ROOT)
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# -- adding static(STATIC_URL) enables app static files with gunicorn, but debug_toolbar static files are not found 

# -- runserver finds app and debug_toolbar static files without the static(STATIC_URL), debug True or False and no DIRS or FINDERS 
# -- gunicorn finds no static files in this state 
# -- adding static(STATIC_URL) allows gunicorn to find app static files, but not debug_toolbar 

if settings.DEBUG:
    print("IS DEBUG")
    import debug_toolbar 
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
