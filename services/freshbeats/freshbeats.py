#!/usr/bin/env python

import os
import sys
from os.path import join, getsize
import subprocess
import shlex
import random
import logging
import traceback
import datetime
from ConfigParser import ConfigParser
import re
import math
# from .device import DeviceManager
from checkout import AlbumManager
import click
import hashlib
# import config.settings_env
from beater.models import Artist, Album, Song, AlbumCheckout, AlbumStatus
import django
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from mutagen import easyid3, id3

sys.path.append(os.path.join(os.path.dirname(__file__), '../../webapp'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'

# BUF_SIZE is totally arbitrary, change for your app!
BUF_SIZE = 65536  # lets read stuff in 64kb chunks!

django.setup()

logging.basicConfig(
    level=logging.DEBUG
)
# fresh_logger = logging.StreamHandler()

logger = logging.getLogger('FreshBeats')
logger.setLevel(logging.DEBUG)

DJANGO_LOGGER = logging.getLogger('django')
DJANGO_LOGGER.setLevel(logging.INFO)
REQUESTS_LOGGER = logging.getLogger('requests')
REQUESTS_LOGGER.setLevel(logging.INFO)
URLLIB3_LOGGER = logging.getLogger('urllib3')
URLLIB3_LOGGER.setLevel(logging.WARN)

# name_logger = logging.getLogger(__name__)

'''
# mount -t vfat /dev/sdb /mnt/phone -o uid=1000,gid=1000,utf8,dmask=027,fmask=137

productid
    708B - windows phone portal
    7089 - windows media sync
    7087 - usb mass storage
    7090 - charge only

Attaching the device to the computer will list it with the chosen function's productid under 'VBoxManage list usbhost' as 'busy'
The device will also show in virtualbox's settings/usb filter menu
Selecting it in the filter menu does nothing, until the VM is powered on, at which point it will be listed as 'captured'
Even after VM power off or removal of the filter, the device will remain 'captured' until virtualbox is closed and restarted

6/26/2015

Installed mtpfs (and gvfs may have already been installed).

gvfs-mount -li

will list all available virtual filesystems - when connected (at least via MTP) an Android device will show.

sudo mtpfs [mount point]

will detect MTP filesystems and do what it can to mount them.

e.g.

sudo mtpfs mtp:host=%5Busb%3A008%2C008%5D

device mounted at:
/run/user/1000/gvfs/mtp:host=%5Busb%3A008%2C008%5D/Internal storage

7/25/2015

plug in android device
ensure device is connected MTP
ensure device shows as mounted
$ gvfs-mount -li | grep Android -A10
create mount point
$ sudo mkidr /media/android
mtpfs mount
$ sudo mtpfs -o allow_other /media/android

8/26/2015

https://wiki.cyanogenmod.org/w/Doc:_sshd

(going through SSH to device rather than MTP - works on wifi!)

but 'shell' user is really weak

1/16/2016

/storage/sdcard0 -> /storage/emulated/legacy (home folder)
/storage/emulated/legacy -> /mnt/shell/emulated/0

'''

album_tags = [
    'album',
    'musicbrainz_artistid',
    'conductor',
    'musicbrainz_albumstatus',
    'artist',
    'media',
    'releasecountry',
    'musicbrainz_albumid',
    'date',
    'albumartist',
    'musicbrainz_albumtype',
    'organization',
    'genre',
    'originaldate'
]
frame_types = {
    'TPE1': 'artist',
    'TALB': 'album',
    'TDRC': 'date',
    'TCON': 'genre',
    'TPUB': 'organization',
    'TPE2': 'albumartist'
}
song_frame_types = ['TIT2', 'TCOM', 'TRCK']
easy_song_frame_types = ['title', 'composer', 'tracknumber']

class Albummeta(object):

    def __init__(self, *args, **kwargs):
        for k in kwargs:
            self.__setattr__(k, kwargs[k])

    def printmeta(self):
        print("")
        print("--- ")
        print("Working Folder: %s" % self.sub_path)
        print("        Artist: %s" % self.artist.name)
        print("         Album: %s" % self.album.name)
        if len(self.album.albumstatus_set.all()) > 0:
            print("         Flags:")
            for f in self.album.albumstatus_set.all():
                print("          - %s" % f.status)
 	else:
	    print("         Flags: none")
        print("        Tracks: %s" % self.track_count)
        print("         Files:")
        for f in self.id3_files:
            print("          - %s" % f)

class FreshBeats(object):

    ''' Fresher beats '''

    device_mount = None
    dev = None

    def __init__(self):

        self.bytes_free = 0
        self.fail = 0

        config = ConfigParser()
        config.read(
            os.path.join(os.path.dirname(__file__), './config/settings.cfg')
        )

        for section in config.sections():
            self.__dict__ = dict(
                self.__dict__.items()
                + {i[0]: i[1] for i in config.items(section)}.items()
            )

        # self.device = DeviceManager(hostname=self.device_hostname,
        # username=self.ssh_username, target_folder=self.beats_target_folder)
        self.album_manager = None

        if os.getenv('FRESHBEATS_MUSIC_PATH'):
            self.music_path = os.getenv('FRESHBEATS_MUSIC_PATH')

        if not os.path.exists(self.music_path):
            logger.error("Music path %s does not exist. Exiting.", self.music_path)
            exit(1)


    def plan_report(self):

        logger.info("Report on device folder '%s'", self.beats_target_folder)

        folders_on_device = self.get_music_folders_on_device(self.beats_target_folder)

        found_on_device = []
        #found_on_device_no_subfolder = []

        for folder_path in folders_on_device:

            #logger.debug("Folder found: %s" % folder_path)

            tup = folder_path.split('/')

            if len(tup) < 2:
                #found_on_device_no_subfolder.append(folder_path)
                continue

            artist = tup[-2]
            album = tup[-1]

            artist_matches = Artist.objects.filter(name=artist)

            if len(artist_matches) > 1:
                logger.debug("Found %s artists for '%s'" % (len(artist_matches), artist))

            for artist_match in artist_matches:
                album_match = Album.objects.filter(artist__name=artist_match.name, name=album).first()
                if album_match:
                    found_on_device.append(album_match)
                    break

        '''
        if len(found_on_device_no_subfolder) > 0:
            logger.warn("%s folders found without proper structure to perform lookup" % len(found_on_device_no_subfolder))
            logger.warn(found_on_device_no_subfolder)
        '''

        if len(found_on_device) == 0:
            logger.warn("No albums found on device")
        else:

            max_album = max([ len(a.name.encode('utf-8')) for a in found_on_device ]) + 1
            max_artist = max([ len(a.artist.name.encode('utf-8')) for a in found_on_device ]) + 1

            logger.info("Albums on Device")

            for a in found_on_device:
                checked_out = a.current_albumcheckout() is not None
                logger.info("{0:<{1}} {2:<{3}} {4:>32} {5:>10}".format(a.name.encode('utf-8'), max_album, a.artist.name.encode('utf-8'), max_artist, a.action, "checked-out" if checked_out else "-"))

        action_albums = Album.objects.filter(~Q(action=Album.DONOTHING), action__isnull=False)
        if len(action_albums) > 0:
            max_album = max([ len(a.name.encode('utf-8')) for a in action_albums ]) + 1
            max_artist = max([ len(a.artist.name.encode('utf-8')) for a in action_albums ]) + 1
        checkout_size = sum([ a.total_size for a in action_albums.filter(Q(action=Album.CHECKOUT) | Q(action=Album.REQUESTCHECKOUT)) ])
        refresh_size = sum([ a.total_size - a.old_total_size for a in action_albums.filter(Q(action=Album.REFRESH)) ])
        checkin_size = sum([ a.total_size for a in action_albums.filter(action=Album.CHECKIN) ])

        logger.info("Albums in Plan")
        for a in action_albums:
            logger.info("{0:<{1}} / {2:<{3}}: {4:>32}".format(a.name.encode('utf-8'), max_album, a.artist.name.encode('utf-8'), max_artist, a.action))

        logger.info("Checking out {0} MB".format(checkout_size/(1024*1024)))
        logger.info("Refreshing {0} MB".format(refresh_size/(1024*1024)))
        logger.info("Checking in {0} MB".format(checkin_size/(1024*1024)))
        net = checkout_size + refresh_size - checkin_size
        direction = "out" if net >= 0 else "in"
        logger.info("Net: {0} MB {1}".format(abs(net)/(1024*1024), direction))

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
        album = None
        added = False
        try:
            album = Album.objects.get(
                artist=artist,
                name=album_name)
            logger.debug(" - album found: %s" % album_name)
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
        if int(album.tracks) == albummeta.track_count and \
                int(album.total_size) == int(albummeta.total_size) and \
                int(album.audio_size) == int(albummeta.audio_size):
            logger.debug(" - metadata match, no changes")
            verified = True
        else:
            logger.info(" - metadata has changed, will reingest album songs")
            if int(album.tracks) != albummeta.track_count:
                logger.info(" - track count (db/disk): %s/%s \
                    ", int(album.tracks), album_meta.track_count)
            if int(album.total_size) != int(albummeta.total_size):
                logger.info(" - total size (db/disk): %s/%s \
                    ", int(album.total_size), int(albummeta.total_size))
            if int(album.audio_size) != int(albummeta.audio_size):
                logger.info(" - audio size (db/disk): %s/%s \
                    ", int(album.audio_size), int(albummeta.audio_size))
        return verified

    def _clear_album_meta(self, album):
        album.tracks = 0
        album.old_total_size = album.total_size
        album.total_size = total_size
        album.audio_size = 0

        # - keep statuses!

        album.save()

        for song in album.song_set.all():
            song.delete()

    def update_db(self, artist_filter=None, sha1_scan=False, purge=False, skip_verification=False):
        ''' Read folders on disk and update database accordingly.'''

        try:

            parent_folder = self.music_path.rpartition('/')[1]
            quit = False
            skip_user_action = False

            for root, dirs, files in os.walk(self.music_path):

                if quit:
                    break

                sub_path = root.replace(self.music_path, "")

                if len(files) == 0:
                    logger.debug(" - %s -> no files, skipping" % sub_path)
                    continue

                root_splits = root.split('/')
                if len(root_splits) > 0:
                    parent = root.split('/')[-1]
                if len(root_splits) > 1:
                    grandparent = root.split('/')[-2]

                parts = [ p for p in sub_path.split('/') if p ]

                if len(parts) == 0:
                    logger.debug(" - %s -> skipping the base path" % sub_path)
                    continue

                logger.info("")
                logger.info("Processing path %s" % sub_path)

                if len(parts) < 2:
                    logger.debug(" - artist only, no album name")
                    artist_name = parts[0]
                    album_name = 'no album'
                elif len(parts) >= 2:
                    # -- assume the last folder is the album name,
                    # -- second to last is the artist
                    # -- extra folders?
                    album_name = parts[-1].strip()
                    artist_name = parts[-2].strip()

                #logger.debug("folder path is type %s while input flag is type %s" % (type(artist), type(artist_filter)))
                if artist_filter and str(artist_filter) != artist_name:
                    logger.debug(" - %s no match for artist filter %s" % (artist_name, str(artist_filter)))
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

                logger.debug(" - path parsed -> artist: %s, album: %s" % (artist_name, album_name))

                total_size = sum(getsize(join(root, name)) for name in all_files)
                audio_size = sum(getsize(join(root, name)) for name in music_files)

                (artist, artist_added) = self._save_artist(artist_name)
                (album, album_added) = self._save_album(artist, album_name, total_size)

                if skip_verification and not artist_added and not album_added:
                    continue

                flags = AlbumStatus.objects.filter(album=album)

                (files_per_val_per_frame, dist, id3_files, val_per_frame_per_file) = self._extract_id3_tags(root)

                user_action = False
                if not skip_user_action:
                    for t in dist:
                        if len(dist[t]) > 1 or any([ v for v in dist[t] if v is None ]):
                            user_action = True
                            break

                albummeta = Albummeta(full_path=root,
                    sub_path=sub_path,
                    artist=artist,
                    album=album,
                    track_count=track_count,
                    total_size=total_size,
                    audio_size=audio_size,
                    id3_files=id3_files,
                    user_action=user_action)

                # - if new, or we made any changes to the album,
                # rewrite the song records
                # - the songs were already cleared (above)
                # if we updated and naturally empty if new
                update_album_meta = not album_added and not self._verify_album_meta(album, albummeta)

                if user_action:
                    while(True):
                        albummeta.printmeta()
                        print("Some discrepancies were detected in the MP3 file tags.")
                        print("What do you want to do?")
                        print("")
                        print("fix ID3 (t)ags")
                        print("    set (f)lags")
                        print("        (c)ontinue")
                        print("        (s)kip all")
                        print("        (q)uit")
                        print("")
                        chosen = raw_input("       ? ")

                        if str(chosen).lower() == "t":
                            self.normalize_id3_tags(albummeta)
                        elif str(chosen).lower() == "f":
                            self.set_flags(albummeta)
                        elif str(chosen).lower() == "s":
                            skip_user_action = True
                            break
                        elif str(chosen).lower() == "c":
                            break
                        elif str(chosen).lower() == "q":
                            quit = True
                            break

                if album_added or update_album_meta:
                    if update_album_meta:
                        self._clear_album_meta(album)
                    logger.debug(" - ingesting %s songs" % track_count)
                    for music_file in music_files:
                        sha1sum = self._get_sha1sum(root, music_file)
                        song = Song(
                            album=album,
                            name=music_file,
                            sha1sum=sha1sum)
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
                elif sha1_scan:
                    logger.info(" - calculating song hashes")
                    for music_file in music_files:
                        sha1sum = self._get_sha1sum(root, music_file)
                        try:
                            logger.debug(" - looking for song %s (album %s) \
                                in DB..", album.encode('utf-8'), music_file.encode('utf-8'))
                            song = Song.objects.get(
                                album=album,
                                name=music_file)
                            if song.sha1sum != sha1sum:
                                song.sha1sum = sha1sum
                                song.save()
                                logger.info(" - SHA1 mismatch, updated %s (%s/%s) \
                                    ", song.encode('utf-8'),
                                    artist.encode('utf-8'),
                                    album.encode('utf-8'))
                        except Song.DoesNotExist as does_not_exist_exc:
                            pass

            if purge:
                # -- when we're all said and done adding,
                # -- delete albums that cannot be found on disk
                # -- (if they've never been checked-out)
                albums = Album.objects.filter(
                    ~Q(albumstatus__status=AlbumStatus.WANTED),
                    albumcheckout__isnull=True
                )
                logger.info("Hard deleting non-existant albums (never checked-out)..")
                for album in albums:
                    if not os.path.exists(self._get_storage_path(album)):
                        # a.delete()
                        logger.info(" - would delete %s/%s", album.artist.name.encode('utf-8'), album.name.encode('utf-8'))

                albums = Album.objects.filter(
                    ~Q(albumstatus__status=AlbumStatus.WANTED)
                )

                logger.info("Soft deleting other albums not found on disk..")

                for album in albums:
                    if not os.path.exists(self._get_storage_path(album)):
                        # a.deleted = True
                        # a.save()
                        logger.info("    Soft-Deleted %s %s",
                                    album.artist.name.encode('utf-8'),
                                    album.name.encode('utf-8'))

        except Exception as update_db_exception:
            message = str(sys.exc_info()[1])
            logging.error(str(sys.exc_info()[0]))
            logging.error(message)
            traceback.print_tb(sys.exc_info()[2])

    def set_flags(self, albummeta):

        flag_menu = { i: c for i, c in enumerate(AlbumStatus.ALBUM_STATUS_CHOICES, 1) }

        while(True):
            for i in flag_menu.keys():
                print("%s (%s) %s: %s" % ("***" if albummeta.album.albumstatus_set.filter(status=flag_menu[i][0]).exists() else "   ", i, flag_menu[i][0], flag_menu[i][1]))
	    print("(q)uit")
            chosen_flag = raw_input(" ?: ")
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

    def _extract_id3_tags(self, album_folder):
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
        files_per_val_per_frame = { frame_types[t]: {} for t in frame_types.keys() }
        val_per_frame_per_file = {}
        for dir, subdirs, files in os.walk(album_folder):
            if dir != album_folder:
                logger.debug("Recursed too var? %s != %s" %(dir, album_folder))
                continue

            for f in files:
                filepath = os.path.join(dir, f)
                try:
                    e = easyid3.EasyID3(filepath)
                    #m = mutagen.File(filepath)
                    if e:
                        val_per_frame_per_file[filepath] = {}
                        logger.debug("   - scanning ID3 tag: %s" % f)
                        for t in album_tags:
                            # -- extraction
                            vals = [None]
                            if t in e:
                                vals = e[t]
                            if len(vals) > 0:
                                val = vals[0]
                                val_per_frame_per_file[filepath][t] = val
                                if t not in files_per_val_per_frame:
                                    files_per_val_per_frame[t] = {}
                                if val not in files_per_val_per_frame[t]:
                                    files_per_val_per_frame[t][val] = []
                                files_per_val_per_frame[t][val].append(f)
                except id3.ID3NoHeaderError:
                    #logger.error(sys.exc_info()[1])
                    pass #? we're not filtering at all
        dist = { t: [ "%s (%s)" % (v, len(files_per_val_per_frame[t][v])) for v in files_per_val_per_frame[t] ] for t in files_per_val_per_frame }
        id3_files = [ f for f in val_per_frame_per_file.keys() ]
        id3_files.sort()
        return (files_per_val_per_frame, dist, id3_files, val_per_frame_per_file)

    def normalize_id3_tags(self, albummeta):

        while(True):

            (files_per_val_per_frame, dist, id3_files, val_per_frame_per_file) = self._extract_id3_tags(albummeta.full_path)

            '''
            files_per_val_per_frame
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

            frame_menu = { i: t for i, t in enumerate(dist.keys(), 1) }
            albummeta.printmeta()
            for i in frame_menu.keys():
                print(" (%s) %s: %s" % (i, frame_menu[i], ", ".join(dist[frame_menu[i]])))
            print(" (q)uit")
            chosen = raw_input("? ")

            if chosen.lower() == 'q':
                break
            elif chosen.isdigit() and int(chosen) in frame_menu:
                easyid_key = frame_menu[int(chosen)]
                albummeta.printmeta()
                print("Fixing %s:" % easyid_key)
                # -- capture one output of the unordered dict and use it for both the question and answer lookup
                frame_val_menu = { n: val for n, val in enumerate(files_per_val_per_frame[easyid_key].keys(), 1) }
                frame_val = None
                while not frame_val:
                    for n in frame_val_menu:
                        print("   (%s) %s" % (n, frame_val_menu[n]))
                        for f in files_per_val_per_frame[easyid_key][frame_val_menu[n]]:
                            print("     - %s" % f)
                    print("   (w)rite in")
                    print("   (s)kip")
                    frame_val_choice = raw_input(" --> Choose: ")
                    if str(frame_val_choice).lower() == 'w':
                        frame_val = raw_input("           : ")
                    elif str(frame_val_choice).lower() == 's':
                        frame_val_choice = None
                        break
                    elif frame_val_choice.isdigit() and int(frame_val_choice) in frame_val_menu:
                        frame_val = unicode(frame_val_menu[int(frame_val_choice)])
                if frame_val:
                    confirmed = False
                    while not confirmed:
                        confirmed_answer = raw_input(" Chosen: %s. Are you sure? (Y/n) " % frame_val)
                        if confirmed_answer == '' or confirmed_answer.lower() == 'y':
                            confirmed = True
                        else:
                            break
                    if confirmed:
                        for f in id3_files:
                            try:
                                e = easyid3.EasyID3(f)
                                current_val = unicode(e[easyid_key]) if easyid_key in e else None
                                if not current_val or current_val != frame_val:
                                    e[easyid_key] = frame_val
                                    logger.info("   - %s -> %s" % (easyid_key, frame_val))
                                else:
                                    logger.info("   - %s OK" % easyid_key)
                                e.save()
                            except id3.ID3NoHeaderError as n:
                                logger.error(n)


        # single_values = { t: files_per_val_per_frame[t] for t in files_per_val_per_frame if len(files_per_val_per_frame[t]) == 1 }
        # for t in single_values:
        #     logger.debug(" - %s: %s" % (t, single_values[t].keys()[0]))
        # multiple_choices = { t: files_per_val_per_frame[t] for t in files_per_val_per_frame if len(files_per_val_per_frame[t]) > 1 }
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

    # - DEVICE

    def remove_album_from_device(self, a):

        logger.info("removing: %s %s" %(a.artist.name.encode('utf-8'), a.name.encode('utf-8')))

        rm_statement = self._get_ssh_statement(r'rm -rf \"%s\"' %(os.path.join(self.beats_target_folder, a.artist.name.encode('utf-8'), a.name.encode('utf-8'))))
        ps = subprocess.Popen(rm_statement)
        (out,err,) = ps.communicate(None)

        logger.info("Remove code: %s" % ps.returncode)

        if ps.returncode == 0:
            current_checkout = a.current_albumcheckout()
            if current_checkout:
                while current_checkout is not None:
                    current_checkout.return_at = timezone.now()
                    current_checkout.save()
                    current_checkout = a.current_albumcheckout()
                    if current_checkout:
                        logger.warn("%s/%s checked out multiple times!" % (a.artist.name, a.name))
            else:
                logger.warn("removing from device, but not checked out!")
            a.action = None
            a.save()

    def copy_album_to_device(self, a):

        artist_folder = os.path.join(self.beats_target_folder, a.artist.name) #join(self.device_mount, self.beats_target_folder, a.artist)

        logger.info(" - adding folder: \"%s\"" %(artist_folder.encode('utf-8')))

        mkdir_statement = self._get_ssh_statement(r'mkdir -p \"%s\"' % artist_folder)
        logger.debug(mkdir_statement)

        ps = subprocess.Popen(mkdir_statement, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out,err,) = ps.communicate(None)

        logger.debug(out)

        if err:
            logger.error(err)

        storage_path = self._get_storage_path(a)
        logger.debug(" - storage path: %s" % storage_path.encode('utf-8'))

        modified_artist_folder = artist_folder.replace(' ', r'\ ').replace("'", r'\'').replace("&", r'\&')
        logger.debug(" - modified artist folder: %s" % modified_artist_folder.encode('utf-8'))

        identify_file_parameter = self._get_ssh_identity_file_parameter()
        cp_statement = r'scp %s -r "%s" %s@%s:"%s/"' % (identify_file_parameter, storage_path, self.ssh_username, self.device_hostname, modified_artist_folder)
        logger.debug(" - %s" % cp_statement.encode('utf-8'))

        ps = subprocess.Popen(shlex.split(cp_statement.encode('utf-8')), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out,err,) = ps.communicate(None)

        logger.debug(out)

        err = err.replace("void endpwent()(3) is not implemented on Android\n", "")

        if err != "":
            raise Exception("'%s'" % err)

        logger.debug(" - add code: %s" % ps.returncode)

        if ps.returncode == 0:
            ac = AlbumCheckout(album=a, checkout_at=timezone.now())
            ac.save()
            a.action = None
            a.save()

    def get_music_folders_on_device(self, target_folder):

        find_folders_command = self._get_ssh_statement(r'find \"%s\" -type d' %(target_folder))

        logger.info(find_folders_command)

        ps = subprocess.Popen(find_folders_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) #, shell=True, executable='/bin/bash')

        (out, err,) = ps.communicate(None)

        if err:
            logger.error(err)

        folders = [ f.replace("%s/" % target_folder, '') for f in out.split('\n') if f and f != target_folder ]

        return folders

    def is_album_on_device(self, album):

        artist_folder = os.path.join(self.beats_target_folder, album.artist.name, album.name)

        find_album_command = self._get_ssh_statement(r'find \"%s\"' %(artist_folder))
        get_line_count_command = self._get_ssh_statement(r'wc -l')

        ps_find = subprocess.Popen(find_album_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ps_count = subprocess.Popen(get_line_count_command, stdin=ps_find.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        (out_count,err_count,) = ps_count.communicate(None)
        (out_find,err_find,) = ps_find.communicate(None)

        return int(out_count) > 1

    def get_free_bytes(self):

        #ps = subprocess.Popen('df -k'.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        #ps = subprocess.Popen(('grep ' + self.device_mount).split(' '), stdin=ps.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        df_cmd = self._get_ssh_statement("df")
        logger.debug(df_cmd)

        grep_emulated = shlex.split("grep emulated")
        logger.debug(grep_emulated)

        ps1 = subprocess.Popen(df_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ps2 = subprocess.Popen(grep_emulated, stdin=ps1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        (out1, err1,) = ps1.communicate(None)
        (out, err,) = ps2.communicate(None)

        logger.debug("ssh return code: %s" % ps1.returncode)
        logger.debug("grep return code: %s" % ps2.returncode)

        if out:
            logger.info("out:")
            logger.error(out)

        if err:
            logger.info("err:")
            logger.error(err)

        if not out and not err:
            raise Exception("no out or err in get_free_bytes!")

        # - Filesystem               Size     Used     Free   Blksize
        # - /mnt/shell/emulated     12G     8.5G     3.5G   4096
        parts = [p for p in out.split(' ') if p != '']
        free = parts[3]

        match = re.search(r'([0-9\.]+)([A-Z])', free)

        size = match.group(1)
        unit = match.group(2)

        unit_multiplier = {'G': math.pow(1024, 3), 'M': math.pow(1024, 2), 'K': math.pow(1024, 1)}

        size_in_bytes = int(math.floor(float(size)*unit_multiplier[unit]))

        logger.debug("free space: %s MB (%s bytes)" % (int(math.floor(float(size_in_bytes)/unit_multiplier['M'])), size_in_bytes))

        return size_in_bytes

    # - END DEVICE

    def _get_ssh_statement(self, command):

        identify_file_parameter = self._get_ssh_identity_file_parameter()
        statement = r'ssh %s %s@%s "%s"' %(identify_file_parameter, self.ssh_username, self.device_hostname, command)

        # - removing encode('utf-8') here because we may be doubling up encoding on string literals passed in to this function
        return shlex.split(statement) # .encode('utf-8'))

    def _get_ssh_identity_file_parameter(self):

        user = self._whoami()

        logger.debug("acting user: %s" % user)

        ssh_key = ''

        if user == self.web_user and self.ssh_key_path:
            ssh_key = "-i %s -o StrictHostKeyChecking=no" % self.ssh_key_path

        return ssh_key

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

    def _get_storage_path(self, album):

        if album.name == 'no album':
            return join(self.music_path, album.artist.name.encode('utf-8'))

        return join(self.music_path, album.artist.name.encode('utf-8'), album.name.encode('utf-8'))

    def _pick_random_fill_albums(self):

        # - we want to keep at least one mix-it-up-rated album
        # - if we aren't renewing one, pick one to check out
        any_kept_mixins = Album.objects.filter(action__in=[Album.DONOTHING, Album.REFRESH], rating=Album.MIXITUP, albumcheckout__isnull=False, albumcheckout__return_at__isnull=True).exists()

        if not any_kept_mixins:

            new_mixins = Album.objects.filter((Q(albumcheckout__isnull=True) | (Q(albumcheckout__isnull=False) & Q(albumcheckout__return_at__isnull=False))), rating=Album.MIXITUP)
            new_mixin_list = list(new_mixins)

            if len(new_mixin_list) > 0:
                new_mixin = random.choice(new_mixin_list)
                logger.info("Registering a mix-it-up album...")
                if not self.album_manager.checkout_album(new_mixin):
                    logger.warn("Rejected checkout of %s/%s" % (new_mixin.artist.name, new_mixin.name))

        loveit_albums = Album.objects.filter(rating=Album.LOVEIT, action=None)
        never_checked_out_albums = Album.objects.filter(albumcheckout__isnull=True, action=None)
        unrated_albums = Album.objects.filter(rating=Album.UNRATED, action=None, albumstatus__isnull=True)

        album_lists = [loveit_albums, never_checked_out_albums, unrated_albums]

        fails = 10

        while True:
            random_list = random.choice(album_lists)
            if len(random_list) == 0:
                album_lists.remove(random_list)
                continue
            album = random.choice(random_list)
            logger.info("Registering a random album...")
            if not self.album_manager.checkout_album(album):
                fails = fails - 1
                logger.warn("Rejected checkout of %s/%s - attempts left: %s" % (album.artist.name, album.name, fails))
            if fails <= 0:
                break

        self.album_manager.send_status_to_logger()

    def validate_plan(self):
        # -- validate the plan
        device_free_bytes = self.get_free_bytes()
        margin = int(self.free_space_mb)*1024*1024
        self.album_manager = AlbumManager(free_bytes_margin=margin, device_free_bytes=device_free_bytes)
        self.album_manager.validate_plan()

    def apply_plan(self, new_randoms=True):

        try:

            self.validate_plan()

            if new_randoms:
                self._pick_random_fill_albums()

            remove_albums = Album.objects.filter(action=Album.CHECKIN)

            for r in remove_albums:
                self.remove_album_from_device(r)

            refresh_albums = Album.objects.filter(action=Album.REFRESH)

            for u in refresh_albums:
                self.remove_album_from_device(u)
                self.copy_album_to_device(u)

            sticky_albums = Album.objects.filter(sticky=True)

            for s in sticky_albums:
                #self.remove_album_from_device(s)
                if not self.is_album_on_device(s):
                    logger.info("Sticky album %s missing" % s)
                    self.copy_album_to_device(s)
                else:
                    logger.info("Sticky album %s already present, moving on.." % s)

            add_albums = Album.objects.filter(action=Album.CHECKOUT)

            for a in add_albums:
                self.copy_album_to_device(a)

            nothing_albums = Album.objects.filter(action=Album.DONOTHING)

            for a in nothing_albums:
                a.action = None
                a.save()
        except:
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])

    def _whoami(self):

        ps = subprocess.Popen(shlex.split("whoami"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err,) = ps.communicate(None)

        if err:
            logger.error(err)
        #logger.info("I am out: %s" % out)
        #logger.info("I am err: %s" % err)

        return out

@click.command()
@click.option('--ingest', '-i', is_flag=True, help='Ingest new music on disk.')
@click.option('--artist_filter', '-t', 'artist_filter', default=None, help='Narrows actions to artist name given')
@click.option('--sha1_scan', '-s', is_flag=True, help='Test existing songs for SHA1 match.')
@click.option('--report', '-r', is_flag=True, help='Report on device status and copy plan.')
@click.option('--validate_plan', '-v', is_flag=True, help='Validates album copy plan.')
@click.option('--apply_plan', '-a', is_flag=True, help='Apply copy plan to device.')
@click.option('--new_randoms', '-n', is_flag=True, help='Try to fit new random albums during "apply".')
@click.option('--purge', '-g', is_flag=True, help='Purge disk and database of not-found items.')
@click.option('--free', '-f', is_flag=True, help='Show device free information.')
@click.option('--skip_verification', '-l', is_flag=True, help='Skip verification of database information with files on disk.')
def main(ingest, artist_filter, sha1_scan, report, validate_plan, apply_plan, new_randoms, purge, free, skip_verification):

    try:

        f = FreshBeats()

        if ingest:
            f.update_db(artist_filter=artist_filter, sha1_scan=sha1_scan, purge=purge, skip_verification=skip_verification)

        if validate_plan:
            f.validate_plan()

        if apply_plan:
            f.apply_plan(new_randoms=new_randoms)

        if report:
            logger.info("Reporting!")
            f.plan_report()

        if free:
            f.get_free_bytes()

    except:
        logger.error(sys.exc_info()[0])
        logger.error(sys.exc_info()[1])
        traceback.print_tb(sys.exc_info()[2])

if __name__ == "__main__":
    main()
