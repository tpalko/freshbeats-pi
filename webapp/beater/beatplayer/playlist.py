import random
import logging
from datetime import datetime, timedelta
from django.db.models import Q
from django.template.loader import render_to_string
from beater.models import PlaylistSong, Playlist as PlaylistModel

logger = logging.getLogger()

# class PlaylistBacking():
#     pass 
# 
# class DatabaseBacking(PlaylistBacking):
# 
#     def get_current(self):
#         return PlaylistSong.objects.filter(is_current=True).first()
#     def get_last(self):
#         return PlaylistSong.objects.all().order_by('-queue_number').first()
#     def get_random(self):
#         return random.choice(PlaylistSong.objects.all()) 
#     def get_next(self):
#         return PlaylistSong.objects.filter(queue_number__gt=self.current_playlistsong.queue_number).order_by('queue_number').first()
#     def get_first(self):
#         return PlaylistSong.objects.all().order_by('queue_number').first()
#     def get_remaining(self):
#         return PlaylistSong.objects.filter(queue_number__gt=self.current_playlistsong.queue_number)
# 
# class EmptyBacking(PlaylistBacking):
#     pass
# 

class PlaylistHelper():
    '''
    Note: these functions specifically are not expected to have "selected playlist" awareness. Requests originate from non-user service components, so no session.
    '''
    
    @staticmethod 
    def playlist(playlist_id):
        return PlaylistModel.objects.get(pk=playlist_id)
        
    @staticmethod
    def playlistsongs(playlist_id=None):
        return PlaylistSong.objects.filter(playlist_id=playlist_id or self.playlist_id).order_by('queue_number');
        
class Playlist():
    '''
    Playlist maintains a queue and a cursor.
    '''
    
    __instances = {}
    playlist_id = None 
    
    @staticmethod
    def getInstance(playlist_id):
        if playlist_id not in Playlist.__instances or Playlist.__instances[playlist_id] == None:
            Playlist(playlist_id=playlist_id)
        return Playlist.__instances[playlist_id]         
    
    def __init__(self, *args, **kwargs):
        if kwargs['playlist_id'] in Playlist.__instances and Playlist.__instances[kwargs['playlist_id']] != None:
            raise Exception("Call Playlist.getInstance() for singleton")
        else:
            self.playlist_id = kwargs['playlist_id']            
            Playlist.__instances[self.playlist_id] = self 
        
    def _play_count_filter(self, playlistsongs):
        if len(playlistsongs) > 0:
            play_count_array = [ s.song.play_count for s in playlistsongs ]
            avg = sum(play_count_array) / len(play_count_array)
            logger.debug("average play count: %s" % avg)
            return playlistsongs.filter(play_count__lte=avg)
        return playlistsongs 
        
    def _age_filter(self, playlistsongs):
        if len(playlistsongs) > 0:
            now = datetime.now()                
            age_array = [ 0 if not s.last_played_at else (now - s.last_played_at).seconds for s in playlistsongs ]
            avg = sum(age_array) / len(age_array)
            logger.debug("average age in seconds: %s" % avg)
            return playlistsongs.filter(Q(last_played_at__lte=(now - timedelta(seconds=avg)))|Q(last_played_at__isnull=True))
        return playlistsongs 
    
    # def _set_current_playlistsong(self, playlistsong):
    #     current_playlistsong = self.get_current_playlistsong()
    #     if current_playlistsong:
    #         current_playlistsong.is_current = False
    #         current_playlistsong.save()
    #     playlistsong.is_current = True
    #     playlistsong.save()
    
    def _get_previous_playlistsongs(self, current_playlistsong):
        return PlaylistSong.objects.filter(playlist_id=self.playlist_id, queue_number__lt=current_playlistsong.queue_number)
            
    def _get_remaining_playlistsongs(self, current_playlistsong):
        remaining = []
        if current_playlistsong:
            remaining = PlaylistSong.objects.filter(playlist_id=self.playlist_id, queue_number__gt=current_playlistsong.queue_number)
        if len(remaining) == 0:
            remaining = PlaylistSong.objects.filter(playlist_id=self.playlist_id)
        return remaining
    
    def _bump_remaining_playlistsongs(self, current_playlistsong, bump_count=1):
        # -- bump the queue number of all future songs
        next_playlistsongs = self._get_remaining_playlistsongs(current_playlistsong)
        for playlistsong in next_playlistsongs:
            playlistsong.queue_number = playlistsong.queue_number + bump_count
            playlistsong.save()        
            
    def advance_cursor(self, current_playlistsong, to_playlistsongid=None, shuffle=False):
        
        cursor_set = False 
        new_playlistsong = None 
        
        logger.debug("Advancing playlist (shuffle: %s) from %s" % (shuffle, current_playlistsong))
        
        if to_playlistsongid:
            new_playlistsong = PlaylistSong.objects.filter(id=to_playlistsongid).first()
        elif shuffle:
            skip = Q()
            if current_playlistsong:
                skip = ~Q(queue_number=current_playlistsong.queue_number)
            valid_playlistsongs = PlaylistSong.objects.filter(Q(playlist_id=self.playlist_id) & skip)
            logger.debug("%s valid playlistsongs" % len(valid_playlistsongs))
            new_playlistsong = random.choice(self._age_filter(self._play_count_filter(valid_playlistsongs)))
            if not new_playlistsong:
                new_playlistsong = random.choice(valid_playlistsongs)
        elif current_playlistsong:
            new_playlistsong = self._get_remaining_playlistsongs(current_playlistsong).order_by('queue_number').first()
        else:
            new_playlistsong = PlaylistSong.objects.filter(Q(playlist_id=self.playlist_id)).order_by('queue_number').first()
        
        if new_playlistsong is not None:
            logger.debug(" -- selected playlistsong %s" % new_playlistsong.id)
        #     self._set_current_playlistsong(new_playlistsong)
        #     cursor_set = True 
        
        return new_playlistsong
    
    def back_up_cursor(self, current_playlistsong):
        previous_playlistsong = None 
        if current_playlistsong:
            previous_playlistsong = self._get_previous_playlistsongs(current_playlistsong).order_by('-queue_number').first()
        if not previous_playlistsong:
            previous_playlistsong = PlaylistSong.objects.order_by('-queue_number').first()
        return previous_playlistsong
    
    # def get_current_playlistsong(self):
    #     return PlaylistSong.objects.filter(is_current=True).first()        
    
    def _renumber_playlistsong_queue(self):
        playlistsongs = PlaylistSong.objects.filter(playlist_id=self.playlist_id).order_by('queue_number')
        for i, ps in enumerate(playlistsongs, 1):
            ps.queue_number = i 
            ps.save()
    
    def increment_current_playlistsong_play_count(self, current_playlistsongid):
        current_playlistsong = PlaylistSong.objects.get(pk=current_playlistsongid)
        if current_playlistsong:
            logger.debug("Incrementing current song count and last played: %s (%s)" % (current_playlistsong.song.name, current_playlistsong.id))
            current_playlistsong.play_count = current_playlistsong.play_count + 1
            current_playlistsong.song.play_count = current_playlistsong.song.play_count + 1
            current_playlistsong.last_played_at = datetime.now()
            current_playlistsong.song.last_played_at = datetime.now()
            current_playlistsong.save()
    
    def determine_queue_number(self, increment=None, current_playlistsong=None):
        '''        
        1. append, don't care about current, add 1 to max 
            - increment never passed 
            - current never passed 
        2. insert, add given increment to current, current being 0 if None 
            - increment always passed: 1-n
            - current always passed, sometimes None 
        '''
        queue_number = 1
        if increment and current_playlistsong:
            queue_number = current_playlistsong.queue_number + increment
        elif increment:
            queue_number = increment 
        else:
            songs = PlaylistSong.objects.filter(playlist_id=self.playlist_id).order_by('-queue_number')
            if songs.count() > 0:
                queue_number = songs.first().queue_number + 1
        return queue_number 
    
    def _add_song(self, song, queue_number):
        new_playlistsong = PlaylistSong(song=song, queue_number=queue_number, playlist_id=self.playlist_id)
        new_playlistsong.save()
                
    def add_song_to_playlist(self, song):        
        self._add_song(song, queue_number=self.determine_queue_number())

    def add_album_to_playlist(self, album):
        for i, song in enumerate(album.song_set.all(), 1):
            self._add_song(song, queue_number=self.determine_queue_number())
    
    def add_artist_to_playlist(self, artist):
        for i, album in enumerate(artist.album_set.all(), 1):
            for j, song, in enumerate(album.song_set.all(), 1):
                self._add_song(song, queue_number=self.determine_queue_number())
    
    def remove_song(self, playlistsongid):        
        playlistsong = PlaylistSong.objects.get(pk=playlistsongid)
        if playlistsong and playlistsong.playlist.id == int(self.playlist_id):
            # for player in playlistsong.player_set.order_by('-parent_id'):
            #     logger.info("Removing player %s" % (player.id))
            #     player.delete()
            logger.info("Removing song %s (%s) from playlist %s" % (playlistsong.song.name, playlistsong.id, playlistsong.playlist.id))
            playlistsong.delete()
        else:
            logger.info("Not removing song from playlist. Song: %s Playlist ID %s in context %s" % (playlistsong.song.name if playlistsong else "null", playlistsong.playlist.id, self.playlist_id))
    
    def remove_album(self, albumid):        
        playlistsongs = PlaylistSong.objects.filter(playlist_id=self.playlist_id, song__album__id=albumid)
        for playlistsong in playlistsongs:
            logger.info("Removing album %s / song %s (%s) from playlist %s" % (playlistsong.song.album.name, playlistsong.song.name, playlistsong.id, playlistsong.playlist.id))
            playlistsong.delete()
    
    def remove_artist(self, artistid):        
        playlistsongs = PlaylistSong.objects.filter(playlist_id=self.playlist_id, song__album__artist__id=artistid)
        for playlistsong in playlistsongs:
            logger.info("Removing artist %s / song %s (%s) from playlist %s" % (playlistsong.song.album.artist.name, playlistsong.song.name, playlistsong.id, playlistsong.playlist.id))
            playlistsong.delete()
            
    def splice_song(self, song, current_playlistsong):
        self._bump_remaining_playlistsongs(current_playlistsong, 1)
        self._add_song(song, queue_number=self.determine_queue_number(increment=1, current_playlistsong=current_playlistsong))

    def splice_album(self, album, current_playlistsong):        
        song_count = album.song_set.count()
        self._bump_remaining_playlistsongs(current_playlistsong, song_count)
        # -- splice in the album as the next queue numbers 
        for i, song in enumerate(album.song_set.all(), 1):
            self._add_song(song, queue_number=self.determine_queue_number(increment=i, current_playlistsong=current_playlistsong))

    def splice_artist(self, artist, current_playlistsong):
        song_count = sum([ album.song_set.count() for album in artist.album_set.all() ])
        self._bump_remaining_playlistsongs(current_playlistsong, song_count)
        bump = 0
        for i, album in enumerate(artist.album_set.all(), 1):
            for j, song, in enumerate(album.song_set.all(), 1):
                bump = bump + 1
                self._add_song(song, queue_number=self.determine_queue_number(increment=bump, current_playlistsong=current_playlistsong))
                
    
        
    
