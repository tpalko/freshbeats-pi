from django.conf.urls import patterns, include, url
from django.conf import settings
from django.conf.urls.static import static

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',    
    url(r'^$', 'beater.views.home', name='home'),
    url(r'^album_filter/(?P<filter>[a-z0-9]+)$', 'beater.views.album_filter'),
    url(r'^album/(?P<albumid>[0-9]+)$', 'beater.views.album', name='album'),
    url(r'^player_command$', 'beater.views.player_command'),    
    url(r'^player_status$', 'beater.views.player_status'),
    url(r'^survey$', 'beater.views.survey'),
    url(r'^survey_post$', 'beater.views.survey_post'),
    url(r'^admin/', include(admin.site.urls))    
) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
