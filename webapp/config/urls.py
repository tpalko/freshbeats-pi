from django.conf.urls import patterns, include, url
from django.conf import settings
from django.conf.urls.static import static

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',    
    url(r'^$', 'beater.views.home', name='home'),
    url(r'^search/$', 'beater.views.search'),
    url(r'^playlist/$', 'beater.views.playlist'),
    url(r'^mobile/$', 'beater.views.mobile'),
    url(r'^config/$', 'beater.views.config'),
    url(r'^survey/$', 'beater.views.survey'),
    url(r'^albums/$', 'beater.views.albums'),
    url(r'^album/(?P<albumid>[0-9]+)/$', 'beater.views.album', name='album'),
    
    #url(r'^album_filter/filter/(?P<filter>[a-z0-9]+)/$', 'beater.views.album_filter'),
    #url(r'^album_filter/letter/(?P<letter>[a-z0-9])/$', 'beater.views.album_letter'),   
    
    url(r'^player/(?P<command>[a-zA-Z]+)/album/(?P<albumid>[0-9]+)/$', 'beater.views.player'),
    url(r'^player/(?P<command>[a-zA-Z]+)/song/(?P<songid>[0-9]+)/$', 'beater.views.player'),
    url(r'^player/(?P<command>[a-zA-Z]+)/$', 'beater.views.player'),
    url(r'^command/(?P<type>[a-zA-Z]+)/$', 'beater.views.command'),    
    url(r'^survey_post/$', 'beater.views.survey_post'),    
    url(r'^get_search_results/$', 'beater.views.get_search_results'),
    url(r'^player_complete/$', 'beater.views.player_complete'),
    url(r'^player_status_and_state/$', 'beater.views.player_status_and_state'),
        
    url(r'^admin/', include(admin.site.urls))    
) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
