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
from beater import views

urlpatterns = [
    url(r'^$', views.home, name='home'),
    url(r'^search/$', views.search, name='search'),
    url(r'^playlist/$', views.playlist, name='playlist'),
    url(r'^mobile/$', views.mobile, name='mobile'),
    url(r'^report/$', views.report, name='report'),
    url(r'^config/$', views.config, name='config'),
    url(r'^survey/$', views.survey, name='survey'),
    url(r'^albums/$', views.albums, name='albums'),
    url(r'^album/(?P<albumid>[0-9]+)/$', views.album, name='album'),
    
    #url(r'^album_filter/filter/(?P<filter>[a-z0-9]+)/$', views.album_filter),
    #url(r'^album_filter/letter/(?P<letter>[a-z0-9])/$', views.album_letter),   
    
    url(r'^player/(?P<command>[a-zA-Z]+)/album/(?P<albumid>[0-9]+)/$', views.player, name='album_command'),
    url(r'^player/(?P<command>[a-zA-Z]+)/song/(?P<songid>[0-9]+)/$', views.player, name='song_command'),
    url(r'^player/(?P<command>[a-zA-Z]+)/$', views.player, name='player'),
    url(r'^command/(?P<type>[a-zA-Z]+)/$', views.command, name='command'),    
    url(r'^survey_post/$', views.survey_post, name='survey_post'),    
    url(r'^get_search_results/$', views.get_search_results, name='get_search_results'),
    url(r'^player_complete/$', views.player_complete, name='player_complete'),
    url(r'^player_status_and_state/$', views.player_status_and_state, name='player_status_and_state'),
        
    url(r'^admin/', include(admin.site.urls))
]
