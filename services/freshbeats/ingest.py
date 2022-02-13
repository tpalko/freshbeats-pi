#!/usr/bin/env python

import re
import json
import os
import sys
from os.path import join, getsize
import logging
import traceback
from configparser import ConfigParser
import click
import hashlib

import django
from django.conf import settings
from django.db.models import Q

# BUF_SIZE is totally arbitrary, change for your app!
BUF_SIZE = 65536  # lets read stuff in 64kb chunks!

sys.path.append(join(os.path.dirname(__file__), '../../webapp'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'

print("setting up")
django.setup()
from beater.models import Artist, Album, Song, AlbumCheckout, AlbumStatus
from mutagen import easyid3, id3

sys.path.append(os.path.dirname(__file__))
from common import get_storage_path

# logging.basicConfig(
#     format='%(log_color)s[ %(levelname)7s ] %(asctime)s %(name)s %(filename)12s:%(lineno)-4d %(message)s'
# )
if __file__:
    print(f'creating logger as {__name__}')
    logger = logging.getLogger(__name__)
else:
    print(f'creating logger as services.ingest')
    logger = logging.getLogger('services.ingest')

logger.setLevel(logging.DEBUG)

logger.fatal(os.getenv('DJANGO_LOG_LEVEL'))

# DJANGO_LOGGER = logging.getLogger('django')
# DJANGO_LOGGER.setLevel(logging.INFO)
# REQUESTS_LOGGER = logging.getLogger('requests')
# REQUESTS_LOGGER.setLevel(logging.INFO)
# URLLIB3_LOGGER = logging.getLogger('urllib3')
# URLLIB3_LOGGER.setLevel(logging.WARN)

album_frame_types = [
    'album',
    'conductor',
    'musicbrainz_albumstatus',
    'artist',
    'media',
    'releasecountry',
    'albumartist',
    'musicbrainz_albumtype',
    'originaldate',
    'organization',
    'genre',
    'musicbrainz_albumid',
    'date',
    'musicbrainz_trmid',
    'musicbrainz_artistid'
]

album_database_frame_types = [
    'organization',
    'genre',
    'musicbrainz_albumid',
    'date',
    'musicbrainz_trmid'
]

artist_database_frame_types = [
    'musicbrainz_artistid'
]

# -- idv3 tags that are also database columns 
# -- we can set these in the database 
# -- and track variation in the tags over time 
song_database_frame_types = [
    'title', 
    'musicbrainz_trackid', 
    'tracknumber'
]

# album_tags = [
#     'album',
#     'musicbrainz_artistid',
#     'conductor',
#     'musicbrainz_albumstatus',
#     'artist',
#     'media',
#     'releasecountry',
#     'musicbrainz_albumid',
#     'date',
#     'albumartist',
#     'musicbrainz_albumtype',
#     'organization',
#     'genre',
#     'originaldate',
#     'musicbrainz_trmid'
# ]

frame_types = {
    'TPE1': 'artist',
    'TALB': 'album',
    'TDRC': 'date',
    'TCON': 'genre',
    'TPUB': 'organization',
    'TPE2': 'albumartist'
}
# song_frame_types = ['TIT2', 'TCOM', 'TRCK']
# easy_song_frame_types = ['title', 'musicbrainz_trackid', 'tracknumber']
# artist_frame_types = ['musicbrainz_artistid']

class Albummeta(object):

    def __init__(self, *args, **kwargs):
        for k in kwargs:
            self.__setattr__(k, kwargs[k])

    def printmeta(self):
        print("")
        print("--- ")
        print(("Working Folder: %s" % self.sub_path))
        print(("        Artist: %s" % self.artist.name))
        print(("         Album: %s" % self.album.name))
        if len(self.album.albumstatus_set.all()) > 0:
            print("         Flags:")
            for f in self.album.albumstatus_set.all():
                print(("          - %s" % f.status))
        else:
            print("         Flags: none")
        print(("        Tracks: %s" % self.track_count))
        print("         Files:")
        for f in self.id3_files:
            print(("          - %s" % f))

class Ingest(object):

    ''' Fresher beats '''

    def __init__(self, *args, **kwargs):

        logger.debug(json.dumps(kwargs, indent=4))
         
        self.artist_filter = kwargs['artist_filter'] if 'artist_filter' in kwargs else None
        self.tags_menu = kwargs['tags_menu'] if 'tags_menu' in kwargs else False
        self.sha1_scan = kwargs['sha1_scan'] if 'sha1_scan' in kwargs else False
        self.id3_scan = kwargs['id3_scan'] if 'id3_scan' in kwargs else False
        self.purge = kwargs['purge'] if 'purge' in kwargs else False
        self.skip_verification = kwargs['skip_verification'] if 'skip_verification' in kwargs else False
        
        config_file = join(os.path.dirname(__file__), './config/settings.cfg')
        config = ConfigParser()
        logger.info(f'Loading {config_file}')
        config.read(config_file)

        for section in config.sections():
            for i in config.items(section):
                logger.debug(f'setting {i[0]}: {i[1]}')
                self.__setattr__(i[0], i[1])

        if os.getenv('FRESHBEATS_MUSIC_PATH'):
            self.music_path = os.getenv('FRESHBEATS_MUSIC_PATH')

        if not os.path.exists(self.music_path):
            logger.error("Music path %s does not exist. Exiting.", self.music_path)
            exit(1)
                
    def _save_artist(self, artist_name):
        artist = None
        added = False
        try:
            artist = Artist.objects.get(name=artist_name)
            logger.debug(" - db artist %s (%s) found" % (artist.name.encode('utf-8'), artist.id))
        except Artist.DoesNotExist as does_not_exist_exc:
            artist = Artist(name=artist_name)
            artist.save()
            logger.info(" - new artist saved: %s", artist.name.encode('utf-8'))
            added = True
        return (artist, added)

    def _save_album(self, artist, album_name, total_size):
        '''If not found by artist and album name, insert a new (empty) record'''
        album = None
        added = False
        try:
            album = Album.objects.get(
                artist=artist,
                name=album_name)
            logger.debug(" - album found: %s" % album_name)
            if album.has_status(AlbumStatus.WANTED):
                album.remove_status(AlbumStatus.WANTED)
                album.save()                
        except Album.DoesNotExist as d:
            album = Album(
                artist=artist,
                name=album_name,
                tracks=0,
                total_size=total_size,
                audio_size=0,
                old_total_size=0,
                rating=Album.UNRATED)
            album.save()
            logger.info(" - new album saved: %s/%s", artist.name.encode('utf-8'), album_name.encode('utf-8'))
            added = True

        return (album, added)

    def _verify_album_meta(self, album, albummeta):
        verified = False
        if int(album.tracks) == int(albummeta.track_count) and \
                int(album.total_size) == int(albummeta.total_size) and \
                int(album.audio_size) == int(albummeta.audio_size):
            logger.debug(" - metadata match, no changes")
            verified = True
        else:
            logger.info(" - metadata has changed, will reingest album songs")
            if int(album.tracks) != int(albummeta.track_count):
                logger.info(" - track count (db/disk): %s/%s \
                    ", int(album.tracks), int(albummeta.track_count))
            if int(album.total_size) != int(albummeta.total_size):
                logger.info(" - total size (db/disk): %s/%s \
                    ", int(album.total_size), int(albummeta.total_size))
            if int(album.audio_size) != int(albummeta.audio_size):
                logger.info(" - audio size (db/disk): %s/%s \
                    ", int(album.audio_size), int(albummeta.audio_size))
        return verified

    def _clear_album_meta(self, album, total_size):
        album.tracks = 0
        album.old_total_size = album.total_size
        album.total_size = total_size
        album.audio_size = 0

        # - keep statuses!

        album.save()

        for song in album.song_set.all():
            song.delete()
            
    def update_db(self):
        
        ''' Read folders on disk and update database accordingly.'''
        '''
        walk folder and for each stop:
            - determine by folder structure the artist and album 
            - if filtering, skip if filtered 
            - verify there are music files, skip if not 
            - get music/non-music file counts and sizes (file stats)
            - add artist if missing 
            - add album if missing (with total size)
            - if neither was missing and skipping verification, continue 
            - check file stats on disk against database 
            - if file stats mismatch, clear and write stats to database
            - get flags 
            - get id3 tag info from disk
            - check tag distributions for skew 
            - if id3 tag skew, show menu 
            - for each database-relevant id3 tag:
                - if consistent, write to database 
        '''
        try:

            # parent_folder = self.music_path.rpartition('/')[1]
            quit = False
            skip_id3_tag_skew_check = False

            for root, dirs, files in os.walk(self.music_path):

                if quit:
                    break

                sub_path = root.replace(self.music_path, "")

                if len(files) == 0:
                    logger.debug(" - %s -> no files, skipping" % sub_path)
                    continue

                # root_splits = root.split('/')
                # if len(root_splits) > 0:
                #     parent = root_splits[-1]
                # if len(root_splits) > 1:
                #     grandparent = root_splits[-2]

                parts = [ p for p in sub_path.split('/') if p ]

                if len(parts) == 0:
                    logger.debug(" - %s -> skipping the base path" % sub_path)
                    continue

                logger.debug("Processing path %s" % sub_path)

                if len(parts) < 2:
                    logger.debug(" - folder depth of one, assuming artist name, no album name")
                    artist_name = parts[0]
                    album_name = 'no album'
                elif len(parts) >= 2:
                    # -- assume the last folder is the album name,
                    # -- second to last is the artist
                    # -- extra folders?
                    album_name = parts[-1].strip()
                    artist_name = parts[-2].strip()
                
                if self.artist_filter:
                    artist_match = re.search(self.artist_filter.lower(), str(artist_name).lower())
                    album_match = re.search(self.artist_filter.lower(), str(album_name).lower())
                    if not artist_match and not album_match:
                        logger.debug(" - %s no match for artist filter %s" % (artist_name, str(self.artist_filter)))
                        continue

                if len(files) > 0 and all(f in self.skip_files for f in files):
                    logger.debug(" - all files are skip files, skipping")
                    continue

                all_files = files
                music_files = [f for f in files if f[f.rfind("."):].lower()
                    in self.music_file_extensions and f.find("._") < 0
                ]

                track_count = len(music_files)

                if track_count == 0:
                    logger.debug(" - no music tracks, skipping")
                    continue

                logger.debug(" - path parsed -> artist: %s, album: %s, tracks: %s" % (artist_name, album_name, track_count))

                total_size = sum(getsize(join(root, name)) for name in all_files)
                audio_size = sum(getsize(join(root, name)) for name in music_files)

                (artist, artist_added) = self._save_artist(artist_name)
                (album, album_added) = self._save_album(artist, album_name, total_size)

                if self.skip_verification and not artist_added and not album_added:
                    logger.debug(f'Nothing new added and skip verification flag set, skipping..')
                    continue

                flags = AlbumStatus.objects.filter(album=album)

                (files_by_values_by_tag, value_counts_per_tag, id3_files, values_by_tags_by_file) = self._extract_album_id3_tags(root)

                '''
                maybe interesting at this point, we're creating an object that 
                    represents both information from the database 
                    and live-on-disk information 
                it may BEHOOVE US to make a clear demarcation in the process 
                    to say.. here are these files in a folder.. 
                    do as much automatic ingestion as makes sense into the database 
                    for information that is useful to have there (and no more)
                    and then involve the human for things like verifying database-destined 
                    data that cannot be verified programmatically and verifying,
                    adding, or fixing the actual file metadata, tags, etc.
                take a pass into memory
                    
                if there's enough information, or maybe we allow some variable relaxation, save it 
                    - artist name 
                    - album name 
                    - album size on disk 
                    - album track count 
                    - album-level tags (on consensus of song tags, i.e. year, style)
                    - song filenames 
                    - song sizes on disk 
                    - song hash 
                    - song-level tags
                human intervention to verify and fix file metadata 
                    - individual file or blanket tags
                    - 
                '''
                albummeta = Albummeta(full_path=root,
                    sub_path=sub_path,
                    artist=artist,
                    album=album,
                    track_count=track_count,
                    total_size=total_size,
                    audio_size=audio_size,
                    id3_files=id3_files)

                # - if new, or we made any changes to the album,
                # rewrite the song records
                # - the songs were already cleared (above)
                # if we updated and naturally empty if new
                album_file_stats_mismatch = not self._verify_album_meta(album, albummeta)
                
                # -- if album added, all stats and tags are obviously new 
                # -- if stats mismatch, this is effectively a new ingestion, so reset all stats and tags 
                if album_added or album_file_stats_mismatch:
                    self._clear_album_meta(album, total_size)
                    logger.debug(" - ingesting %s songs" % track_count)
                    for music_file in music_files:
                        sha1sum = self._get_sha1sum(root, music_file)
                        song = Song(
                            album=album,
                            name=music_file,
                            sha1sum=sha1sum)                        
                        song_frames = self._get_frames(join(root, music_file), song_database_frame_types)
                        for frame in song_frames.keys():
                            song.__setattr__(frame, song_frames[frame])
                        song.save()
                        album.tracks += 1
                        audio_size = getsize(join(root, music_file))
                        album.audio_size += audio_size
                        album.save()
                        logger.debug(" - %s, %s, %s bytes", music_file, sha1sum, audio_size)
                    if album_added:
                        logger.info(" - inserted %s/%s", album.artist, album)
                    else:
                        logger.info(" - updated %s/%s", album.artist, album)
                else:
                    if self.id3_scan or self.sha1_scan:
                        for song in album.song_set.all():
                            needs_save = False 
                            if self.id3_scan:
                                song_frames = self._get_frames(join(root, song.name), song_database_frame_types)
                                logger.debug(" - read %s frames from %s" % (len(song_frames.keys()), song.name))
                                for frame in song_frames.keys():
                                    db_value = song.__dict__[frame]
                                    if str(db_value) != str(song_frames[frame]):
                                        logger.info("   - %s mismatch (db: %s, file: %s)" % (frame, db_value, song_frames[frame]))
                                        # -- actual value on disk rules 
                                        song.__setattr__(frame, song_frames[frame])
                                        needs_save = True 
                            if self.sha1_scan:
                                logger.info(" - calculating song hash")
                                sha1sum = self._get_sha1sum(root, song.name)
                                if song.sha1sum != sha1sum:
                                    song.sha1sum = sha1sum
                                    logger.info(" - SHA1 mismatch, updated %s (%s/%s) \
                                        ", song.name.encode('utf-8'),
                                        artist.name.encode('utf-8'),
                                        album.name.encode('utf-8'))
                                    needs_save = True 
                            if needs_save:
                                song.save()

                # -- only if we're not planning on showing the menu already 
                # -- and we care about tag skew 
                # -- do we bother to check if...
                
                id3_tag_skew = any([ t for t in value_counts_per_tag if len(value_counts_per_tag[t]) > 1 or len(value_counts_per_tag[t]) == 1 and value_counts_per_tag[t][0] == None ])
                
                # id3_tag_skew = False
                # if not self.tags_menu and not skip_id3_tag_skew_check:
                #     # -- ...any found tags have more than one value?
                #     for t in value_counts_per_tag:
                #         # -- the tag has more than one value 
                #         # -- the tag has a 'None' value 
                #         if len(value_counts_per_tag[t]) > 1 or len([ v for v in value_counts_per_tag[t] if v is None ]) > 0:
                #             # -- and if so, show that menu
                #             id3_tag_skew = True
                #             break

                if not skip_id3_tag_skew_check and (id3_tag_skew or self.tags_menu):
                    while(True):
                        albummeta.printmeta()
                        print("Some discrepancies were detected in the MP3 file tags.")
                        print("What do you want to do?")
                        print("")
                        print("fix ID3 tags for (a)lbum")
                        print("fix ID3 tags for (s)ongs")
                        print("             set (f)lags")
                        print("              do (n)othing for this album")
                        print("   skip this and (d)on't check ID3 tags on remaining albums")
                        print("                 (q)uit")
                        print("")
                        chosen = input("       ? ")

                        if str(chosen).lower() == "a":
                            self.normalize_id3_tags_for_album(albummeta)
                        elif str(chosen).lower() == "s":
                            self.fix_id3_tags_for_songs(albummeta)
                        elif str(chosen).lower() == "f":
                            self.set_flags(albummeta)
                        elif str(chosen).lower() == "d":
                            skip_id3_tag_skew_check = True
                            break
                        elif str(chosen).lower() == "n":
                            break
                        elif str(chosen).lower() == "q":
                            quit = True
                            break
                
                if quit:
                    logger.info("Quitting!")
                    break 
                    
                (files_by_values_by_tag, value_counts_per_tag, id3_files, values_by_tags_by_file) = self._extract_album_id3_tags(root)
                
                # -- go through found tag values in the collection of files 
                # -- and if there is consensus and we're tracking that tag in the database 
                # -- make sure the database has the correct value 
                # -- TODO: should we track the non-consensus state in the database.. just say "uncertain" in the field 
                logger.info("Updating database for consensus tag values:")
                for t in [ t for t in files_by_values_by_tag if t in album_database_frame_types ]:
                    values = files_by_values_by_tag[t].keys()
                    # -- if there is only one value among all files and this is NOT the value represented in the database
                    # -- go ahead and save it 
                    if len(values) == 1 and list(values)[0] is not None and album.__dict__[t] != list(values)[0]:
                        value = list(values)[0]
                        logger.info(" - album frame type %s is consistently '%s', writing to album.." % (t, value))
                        album.__setattr__(t, value)
                        album.save()
                for t in [ t for t in files_by_values_by_tag if t in artist_database_frame_types ]:
                    values = files_by_values_by_tag[t].keys()
                    if len(values) == 1 and list(values)[0] is not None and artist.__dict__[t] != list(values)[0]:
                        value = list(values)[0]
                        logger.info(" - artist frame type %s is consistently '%s', writing to artist.." % (t, value))
                        artist.__setattr__(t, value)
                        artist.save()
                    
            if self.purge:
                # -- when we're all said and done adding,
                # -- delete albums that cannot be found on disk
                # -- (if they've never been checked-out)
                albums = Album.objects.filter(
                    ~Q(albumstatus__status=AlbumStatus.WANTED),
                    albumcheckout__isnull=True
                )
                logger.info("Hard deleting non-existant albums (never checked-out)..")
                logger.info("  - found %s total albums not marked 'wanted' and never checked out" % len(albums))
                for album in albums:
                    if not os.path.exists(join(self.music_path, get_storage_path(album))):
                        logger.info("  - %s/%s missing, would actually hard-delete album from database", album.artist.name.encode('utf-8'), album.name.encode('utf-8'))
                        # a.delete()
                    else:
                        logger.debug("  - %s/%s was found on disk, so not deleting" % (album.artist.name.encode('utf-8'), album.name.encode('utf-8')))

                albums = Album.objects.filter(
                    ~Q(albumstatus__status=AlbumStatus.WANTED)
                )

                logger.info("Soft deleting other albums not found on disk..")
                logger.info("  - found %s total albums not marked 'wanted' but may have been checked out" % len(albums))
                for album in albums:
                    if not os.path.exists(join(self.music_path, get_storage_path(album))):
                        # a.deleted = True
                        # a.save()
                        logger.info("  - %s/%s missing, would actually soft-delete in database", album.artist.name.encode('utf-8'), album.name.encode('utf-8'))
                    else:
                        logger.debug("  - %s/%s was found on disk, so not deleting" % (album.artist.name.encode('utf-8'), album.name.encode('utf-8')))
        
        except django.db.utils.OperationalError as oe:
            message = str(sys.exc_info()[1])
            logging.error(str(sys.exc_info()[0]))
            logging.error(message)
            traceback.print_tb(sys.exc_info()[2])
        except Exception as update_db_exception:
            message = str(sys.exc_info()[1])
            logging.error(str(sys.exc_info()[0]))
            logging.error(message)
            traceback.print_tb(sys.exc_info()[2])

    def set_flags(self, albummeta):

        flag_menu = { i: c for i, c in enumerate(AlbumStatus.ALBUM_STATUS_CHOICES, 1) }

        while(True):
            for i in list(flag_menu.keys()):
                print(("%s (%s) %s: %s" % ("***" if albummeta.album.albumstatus_set.filter(status=flag_menu[i][0]).exists() else "   ", i, flag_menu[i][0], flag_menu[i][1])))
            print("(q)uit")
            chosen_flag = input(" ?: ")

            if chosen_flag.lower() == 'q':
                break

            if chosen_flag.isdigit() and int(chosen_flag) in flag_menu:
                flag = flag_menu[int(chosen_flag)]

            if albummeta.album.albumstatus_set.filter(status=flag[0]).exists():
                albummeta.album.albumstatus_set.filter(status=flag[0]).delete()
                logger.info("%s flag removed from album %s" % (flag[0], albummeta.album.name))
            else:
                albummeta.album.albumstatus_set.create(status=flag[0])
                logger.info("%s flag added to album %s" % (flag[0], albummeta.album.name))

    def _get_frames(self, filepath, types):
        frames = {}
        try:
            e = easyid3.EasyID3(filepath)
            frames = { t: e[t][0] for t in types if t in e and e[t] }
            if 'tracknumber' in frames and frames['tracknumber'].find('/') > 0:
                logger.info("   - found #/# tracknumber format in %s: %s" % (filepath, frames['tracknumber']))
                numer = frames['tracknumber'].split('/')[0]
                frames['tracknumber'] = numer
        except id3.ID3NoHeaderError as n:
            logger.info("   - failed to extract frame types from %s" % filepath)
            pass         
        return frames

    def _get_sha1sum(self, root, filename):

        sha1 = hashlib.sha1()

        with open(join(root, filename), 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                sha1.update(data)

        song_sha1sum = sha1.hexdigest()

        return song_sha1sum
    
    def _extract_file_id3_tags(self, albummeta):
        
        for f in albummeta.id3_files:
            e = easyid3.EasyID3(f)
            
    def _extract_album_id3_tags(self, album_folder):
        # - pass artist and album, or just let it run
        # - for each album, extract:
        #   - per song, common frames and their values
        #   - per common frame, values and songs with each value
        #   - any status flags from the database
        # - draw menu:
        #   - each frame, array of existing values and file count
        #       - choose a frame to fix, displays list of value and filenames
        #           - choose the value to apply to all, write-in, or skip
        #           - applies change, shows results, redraw original menu
        #   - each file + renaming based on ID3 tag
        #   - each possible status + toggle
        #   - skip album
        # -- for each attribute, for each value of that attribute, a list of files 
        files_by_values_by_tag = { frame_types[t]: {} for t in list(frame_types.keys()) }
        # -- for each file, for each attribute of that file, the value 
        values_by_tags_by_file = {}
        id3_files = []
        for dir, subdirs, files in os.walk(album_folder):
            if dir != album_folder:
                logger.debug("Recursed too var? %s != %s" %(dir, album_folder))
                continue

            for f in files:
                filepath = os.path.join(dir, f)
                logger.debug(f'extract id3 tags have {filepath}')
                try:
                    if filepath not in id3_files:
                        logger.debug(f'Added {filepath} to id3_files')
                        id3_files.append(filepath)
                    else:
                        logger.debug(f'{filepath} is already in id3_files')
                    e = easyid3.EasyID3(filepath)
                    #m = mutagen.File(filepath)
                    if e:
                        logger.debug(f'have EasyID3 of {filepath}')                        
                        # print(e)
                        values_by_tags_by_file[filepath] = {}
                        logger.debug("   - scanning ID3 tag: %s" % f)
                        for t in album_frame_types:
                            # -- extraction
                            vals = [None]
                            if t in e:
                                vals = e[t]
                            if len(vals) > 0:
                                val = vals[0]
                                values_by_tags_by_file[filepath][t] = val
                                if t not in files_by_values_by_tag:
                                    files_by_values_by_tag[t] = {}
                                if val not in files_by_values_by_tag[t]:
                                    files_by_values_by_tag[t][val] = []
                                files_by_values_by_tag[t][val].append(f)
                    else:
                        logger.debug(f'EasyID3 did not take on {filepath}')
                except id3.ID3NoHeaderError:
                    #logger.error(sys.exc_info()[1])
                    pass #? we're not filtering at all
        # -- dict of frames and lists of value: # files with that value 
        value_counts_per_tag = { tag: [ "%s (%s)" % (value, len(files_by_values_by_tag[tag][value])) for value in files_by_values_by_tag[tag] ] for tag in files_by_values_by_tag }
        id3_files.sort()
        return (files_by_values_by_tag, value_counts_per_tag, id3_files, values_by_tags_by_file)

    def fix_id3_tags_for_songs(self, albummeta):
        pass 

    def normalize_id3_tags_for_album(self, albummeta):

        while(True):

            (files_by_values_by_tag, value_counts_per_tag, id3_files, values_by_tags_by_file) = self._extract_album_id3_tags(albummeta.full_path)

            '''
            files_by_values_by_tag
            {
                frame:
                {
                    val: [file, file, file],
                    val: [file, file, file]
                },
                frame:
                {
                    val: [file, file, file],
                    val: [file, file, file]
                }
            }
            {
                frame: ["<val>: <count>","<val>: <count>"],
                frame: ["<val>: <count>","<val>: <count>"]
            }
            '''

            frame_menu = { i: t for i, t in enumerate(list(value_counts_per_tag.keys()), 1) }
            albummeta.printmeta()
            for i in list(frame_menu.keys()):
                dist_display = ''
                if len(value_counts_per_tag[frame_menu[i]]) > 1:
                    dist_display = '\n\t'
                    for d in value_counts_per_tag[frame_menu[i]]:
                        dist_display += '%s\n\t' % d 
                else:
                    dist_display = "\n".join(value_counts_per_tag[frame_menu[i]])
                print(" (%s) %s: %s" % (i, frame_menu[i], dist_display))
            print(" (q)uit")
            chosen = input("? ")

            if chosen.lower() == 'q':
                break
            elif chosen.isdigit() and int(chosen) in frame_menu:
                easyid_key = frame_menu[int(chosen)]
                albummeta.printmeta()
                print(("Fixing %s:" % easyid_key))
                print("Choose one value to apply to all tracks.")
                print("If there is not a single value for all tracks but the information shown is not correct, sorry, we don't support that yet.")
                # -- capture one output of the unordered dict and use it for both the question and answer lookup
                frame_val_menu = { n: val for n, val in enumerate(list(files_by_values_by_tag[easyid_key].keys()), 1) }
                frame_val = None
                while not frame_val:
                    for n in frame_val_menu:
                        print(("   (%s) %s" % (n, frame_val_menu[n])))
                        for f in files_by_values_by_tag[easyid_key][frame_val_menu[n]]:
                            print(("     - %s" % f))
                    print("   (w)rite in")
                    print("   (s)kip")
                    frame_val_choice = input(" --> Choose: ")
                    if str(frame_val_choice).lower() == 'w':
                        frame_val = input("           : ")
                    elif str(frame_val_choice).lower() == 's':
                        frame_val_choice = None
                        break
                    elif frame_val_choice.isdigit() and int(frame_val_choice) in frame_val_menu:
                        frame_val = str(frame_val_menu[int(frame_val_choice)])
                if frame_val:
                    confirmed = False
                    while not confirmed:
                        confirmed_answer = input(" Chosen: %s. Are you sure? (Y/n) " % frame_val)
                        if confirmed_answer == '' or confirmed_answer.lower() == 'y':
                            confirmed = True
                        else:
                            break
                    if confirmed:
                        for f in id3_files:
                            try:
                                e = easyid3.EasyID3(f)
                                current_val = str(e[easyid_key]) if easyid_key in e else None
                                if not current_val or current_val != frame_val:
                                    e[easyid_key] = frame_val
                                    logger.info("   - %s -> %s" % (easyid_key, frame_val))
                                else:
                                    logger.info("   - %s OK" % easyid_key)
                                e.save()
                            except id3.ID3NoHeaderError as n:
                                logger.error(n)


        # single_values = { t: files_by_values_by_tag[t] for t in files_by_values_by_tag if len(files_by_values_by_tag[t]) == 1 }
        # for t in single_values:
        #     logger.debug(" - %s: %s" % (t, single_values[t].keys()[0]))
        # multiple_choices = { t: files_by_values_by_tag[t] for t in files_by_values_by_tag if len(files_by_values_by_tag[t]) > 1 }
        # for n, t in enumerate(multiple_choices, 1):
        #     easyid_key = frame_types[t]
        #     print(" - %s" % albummeta)
        #     print(" - %s/%s ID3 multiple choice (%s/%s):" % (n, len(multiple_choices), t, easyid_key))
        #     # -- capture one output of the unordered dict and use it for both the question and answer lookup
        #     choices = { n: val for n, val in enumerate(multiple_choices[t].keys(), 1) }
        #     chosen_val = None
        #     while not chosen_val:
        #         for n in choices:
        #             print("   - (%s) %s" % (n, choices[n]))
        #             for f in multiple_choices[t][choices[n]]:
        #                 print("     - %s" % f)
        #         print("   - (s)kip")
        #         chosen_val = raw_input(" --> Choose: ")
        #         if str(chosen_val).lower() == 's':
        #             chosen_val = None
        #             break
        #         if chosen_val.isdigit():
        #             chosen_val = unicode(choices[int(chosen_val)])
        #     if chosen_val:
        #         for f in id3_files:
        #             try:
        #                 e = mutagen.easyid3.EasyID3(f)
        #                 current_val = unicode(e[easyid_key]) if easyid_key in e else None
        #                 if not current_val or current_val != chosen_val:
        #                     e[easyid_key] = chosen_val
        #                     logger.info("   - %s (%s) -> %s" % (t, easyid_key, chosen_val))
        #                 else:
        #                     logger.info("   - %s OK" % t)
        #                 e.save()
        #             except mutagen.id3.ID3NoHeaderError as n:
        #                 logger.error(n)

@click.command()
@click.option('--artist-filter', '-t', 'artist_filter', default=None, help='Narrows actions to artist name given')
@click.option('--tags-menu', '-m', is_flag=True, help='Force showing the tags menu.')
@click.option('--sha1-scan', '-s', is_flag=True, help='Test existing songs for SHA1 match.')
@click.option('--id3-scan', '-3', is_flag=True, help='Test existing songs for song-specific ID3 tag mismatch')
@click.option('--purge', '-g', is_flag=True, help='Purge disk and database of not-found items.')
@click.option('--skip-verification', '-l', is_flag=True, help='Skip verification of database information with files on disk.')
def main(artist_filter, tags_menu, sha1_scan, id3_scan, purge, skip_verification):

    try:

        config = {
            'artist_filter': artist_filter, 
            'tags_menu': tags_menu, 
            'sha1_scan': sha1_scan, 
            'id3_scan': id3_scan, 
            'purge': purge, 
            'skip_verification': skip_verification
        }
        print(json.dumps(config, indent=4))
        # -- double-star a dict to pass kwargs 
        f = Ingest(**config)
        f.update_db()

    except:
        logger.error(sys.exc_info()[0])
        logger.error(sys.exc_info()[1])
        traceback.print_tb(sys.exc_info()[2])

if __name__ == "__main__":
    main()
