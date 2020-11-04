from django.db.models import Q
from django.template.loader import render_to_string
from ..models import PlaylistSong
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PlaylistBacking():
    pass 

class DatabaseBacking(PlaylistBacking):
    
    def get_current(self):
        return PlaylistSong.objects.filter(is_current=True).first()
    def get_last(self):
        return PlaylistSong.objects.all().order_by('-queue_number').first()
    def get_random(self):
        return random.choice(PlaylistSong.objects.all()) 
    def get_next(self):
        return PlaylistSong.objects.filter(queue_number__gt=self.current_playlistsong.queue_number).order_by('queue_number').first()
    def get_first(self):
        return PlaylistSong.objects.all().order_by('queue_number').first()
    def get_remaining(self):
        return PlaylistSong.objects.filter(queue_number__gt=self.current_playlistsong.queue_number)

class EmptyBacking(PlaylistBacking):
    pass
    
class Playlist():
    '''
    Playlist maintains a queue and a cursor.
    '''
    
    playlist_stale = True 
    playlist_html = None 

    def __init__(self, *args, **kwargs):
        if not self.get_current_playlistsong():
            self.set_current_playlistsong(PlaylistSong.objects.all().order_by('queue_number').first())

    def __str__(self):
        if self.playlist_stale:
            playlistsongs = PlaylistSong.objects.all().order_by('queue_number');
            self.playlist_html = render_to_string("_playlist.html", {'playlistsongs': playlistsongs})
            self.playlist_stale = False 
        return self.playlist_html
    
    def play_count_filter(self, playlistsongs):
        if len(playlistsongs) > 0:
            play_count_array = [ s.song.play_count for s in playlistsongs ]
            avg = sum(play_count_array) / len(play_count_array)
            logger.debug("average play count: %s" % avg)
            return playlistsongs.filter(play_count__lte=avg)
        return playlistsongs 
        
    def age_filter(self, playlistsongs):
        if len(playlistsongs) > 0:
            now = datetime.now()                
            age_array = [ 0 if not s.last_played_at else (now - s.last_played_at).seconds for s in playlistsongs ]
            avg = sum(age_array) / len(age_array)
            logger.debug("average age in seconds: %s" % avg)
            return playlistsongs.filter(Q(last_played_at__lte=(now - timedelta(seconds=avg)))|Q(last_played_at__isnull=True))
        return playlistsongs 
        
    def advance_cursor(self, playlistsongid=None, shuffle=False):

        cursor_set = False 
        new_playlistsong = None 
        
        if playlistsongid:
            new_playlistsong = PlaylistSong.objects.get(pk=playlistsongid)
        elif shuffle:
            valid_playlistsongs = PlaylistSong.objects.all()
            current_playlistsong = self.get_current_playlistsong()
            if current_playlistsong:
                valid_playlistsongs = PlaylistSong.objects.filter(~Q(queue_number=current_playlistsong.queue_number))
            logger.debug("%s valid playlistsongs" % len(valid_playlistsongs))
            new_playlistsong = random.choice(self.age_filter(self.play_count_filter(valid_playlistsongs)))
            if not new_playlistsong:
                new_playlistsong = random.choice(valid_playlistsongs)
        else:
            new_playlistsong = self._get_remaining_playlistsongs().order_by('queue_number').first()
        
        if new_playlistsong:
            self.set_current_playlistsong(new_playlistsong)
            cursor_set = True 
        
        return cursor_set
    
    def back_up_cursor(self):
        cursor_set = False 
        new_playlistsong = self._get_previous_playlistsongs().order_by('-queue_number').first()
        if new_playlistsong:
            self.set_current_playlistsong(new_playlistsong)
            cursor_set = True         
        return cursor_set
        
    def set_current_playlistsong(self, playlistsong):
        current_playlistsong = self.get_current_playlistsong()
        if current_playlistsong:
            current_playlistsong.is_current = False
            current_playlistsong.save()
        playlistsong.is_current = True
        playlistsong.save()
        self.playlist_stale = True
        
    def get_current_playlistsong(self):
        return PlaylistSong.objects.filter(is_current=True).first()
    
    def _get_previous_playlistsongs(self):
        current_playlistsong = self.get_current_playlistsong()
        if current_playlistsong:
            return PlaylistSong.objects.filter(queue_number__lt=current_playlistsong.queue_number)
        else:
            return PlaylistSong.objects.all()
            
    def _get_remaining_playlistsongs(self):
        current_playlistsong = self.get_current_playlistsong()
        remaining = []
        if current_playlistsong:
            remaining = PlaylistSong.objects.filter(queue_number__gt=current_playlistsong.queue_number)
        if len(remaining) == 0:
            remaining = PlaylistSong.objects.all()
        return remaining
        
    def increment_current_playlistsong_play_count(self):
        current_playlistsong = self.get_current_playlistsong()
        if current_playlistsong:
            current_playlistsong.play_count = current_playlistsong.play_count + 1
            current_playlistsong.song.play_count = current_playlistsong.song.play_count + 1
            current_playlistsong.last_played_at = datetime.now()
            current_playlistsong.song.last_played_at = datetime.now()
            current_playlistsong.save()
            self.playlist_stale = True

    def add_song_to_playlist(self, song, queue_number=None):
        if not queue_number:
            queue_number = PlaylistSong.objects.all().order_by('-queue_number').first().queue_number + 1
        new_playlistsong = PlaylistSong(song=song, queue_number=queue_number)
        new_playlistsong.save()
        self.playlist_stale = True 

    def add_album_to_playlist(self, album):
        for i, song in enumerate(album.song_set.all(), 1):
            self.add_song_to_playlist(song)
    
    def add_artist_to_playlist(self, artist):
        for i, album in enumerate(artist.album_set.all(), 1):
            for j, song, in enumerate(album.song_set.all(), 1):
                self.add_song_to_playlist(song)
    
    def _bump_remaining_playlistsongs(self, bump_count=1):
        # -- bump the queue number of all future songs
        next_playlistsongs = self._get_remaining_playlistsongs()
        for playlistsong in next_playlistsongs:
            playlistsong.queue_number = playlistsong.queue_number + bump_count
            playlistsong.save()        
            self.playlist_stale = True
        
    def splice_song(self, song):
        self._bump_remaining_playlistsongs(1)
        current_playlistsong = self.get_current_playlistsong()
        self.add_song_to_playlist(song, current_playlistsong.queue_number + 1)

    def splice_album(self, album):        
        song_count = album.song_set.count()
        self._bump_remaining_playlistsongs(song_count)
        # -- splice in the album as the next queue numbers 
        current_playlistsong = self.get_current_playlistsong()
        for i, song in enumerate(album.song_set.all(), 1):
            self.add_song_to_playlist(song, current_playlistsong.queue_number + i)

    def splice_artist(self, artist):
        song_count = sum([ album.song_set.count() for album in artist.album_set.all() ])
        self._bump_remaining_playlistsongs(song_count)
        bump = 0
        current_playlistsong = self.get_current_playlistsong()
        for i, album in enumerate(artist.album_set.all(), 1):
            for j, song, in enumerate(album.song_set.all(), 1):
                bump = bump + 1
                self.add_song_to_playlist(song, current_playlistsong.queue_number + bump)
