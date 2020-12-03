#!/usr/bin/env python

import os
import sys
from os.path import join
import subprocess
import shlex
import random
import logging
import traceback
import datetime
from configparser import ConfigParser
import re
import math
# from .device import DeviceManager
try:
    from checkout import AlbumManager
except ImportError as e:
    from .checkout import AlbumManager
import click

# import config.settings_env
from beater.models import Artist, Album, Song, AlbumCheckout, AlbumStatus
import django
from django.db.models import Q
from django.utils import timezone
#from django.conf import settings

from . import common

# try:
#     import .common as common 
# except ImportError as e:
#     import common

sys.path.append(join(os.path.dirname(__file__), '../../webapp'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'



django.setup()

logger = logging.getLogger('FreshBeats')
logger.setLevel(logging.INFO)

DJANGO_LOGGER = logging.getLogger('django')
DJANGO_LOGGER.setLevel(logging.INFO)
REQUESTS_LOGGER = logging.getLogger('requests')
REQUESTS_LOGGER.setLevel(logging.INFO)
URLLIB3_LOGGER = logging.getLogger('urllib3')
URLLIB3_LOGGER.setLevel(logging.WARN)

# name_logger = logging.getLogger(__name__)

class Process(object):
    
    web_user = None 
    ssh_key_path = None 
    ssh_username = None 
    device_hostname = None 
    
    def __init__(self, *args, **kwargs):
        for key in kwargs.keys():
            logger.debug("setting %s <= %s" % (key, kwargs[key]))
            self.__setattr__(key, kwargs[key])

    def _whoami(self):
        (ps, out, err) = self.command('whoami')
        return out
        
    def _get_ssh_identity_file_parameter(self):

        user = self._whoami()

        #logger.debug("acting user: %s" % user)

        ssh_parameters = ''
        
        #logger.debug("web_user: %s" % self.web_user)
        if user == self.web_user and self.ssh_key_path:
            ssh_parameters = "-i %s -o StrictHostKeyChecking=no" % self.ssh_key_path
        
        address = "%s@%s" %(self.ssh_username, self.device_hostname)
        
        #logger.debug("parameters: %s" % ssh_parameters)
        #logger.debug("address: %s" % address)
        
        return (ssh_parameters, address)
        
    def _get_ssh_statement(self, command):

        (parameters, address) = self._get_ssh_identity_file_parameter()
        statement = r'ssh %s %s "%s"' %(parameters, address, command)

        # - removing encode('utf-8') here because we may be doubling up encoding on string literals passed in to this function
        return shlex.split(statement) # )
        
    def command(self, command):
        ps = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out,err,) = ps.communicate(None)
        
        #logger.debug(command)
        #logger.debug(out)
        if err:
            logger.error(err)
            
        return (ps, out, err)
        
    def remote_command(self, command, level=0):
        plist = []
        outs = []
        errs = []
        # -- recursively deconstruct the command list, pulling the last one off each time 
        if type(command).__name__ == 'list':
            if len(command) > 1:
                first_commands = command[0:-1]
                logger.debug("passing %s onto recursivity" % first_commands)
                (plist, outs, errs) = self.remote_command(first_commands, level=level+1)                
                command = command[-1]
            else:
                command = command[0]
        # -- the first pass here will be the first command in the list 
        logger.debug("plist length: %s, level %s, command %s" % (len(plist), level, command))
        if len(plist) > 0:
            statement = shlex.split(command)
            ps = subprocess.Popen(statement, stdin=plist[-1].stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (out, err) = plist[-1].communicate(None)
            logger.debug("out: %s" % out)
            logger.debug("err: %s" % err)
            outs.append(out)
            errs.append(err)
        else:
            statement = self._get_ssh_statement(command)
            ps = subprocess.Popen(statement, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        plist.append(ps)
        if level == 0:
            logger.debug("communicate at top level")
            (out, err) = plist[-1].communicate(None)
            logger.debug("out: %s" % out)
            logger.debug("err: %s" % err)
            outs.append(out)
            errs.append(err)
        return (plist, outs, errs)
    
    def copy(self, file, path):
        (parameters, address) = self._get_ssh_identity_file_parameter()
        cp_statement = r'scp -r %s "%s" %s:"%s/"' % (parameters, file, address, path)
        logger.debug(" - %s" % cp_statement)

        ps = subprocess.Popen(shlex.split(cp_statement), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out,err,) = ps.communicate(None)

        err = err.decode().replace("void endpwent()(3) is not implemented on Android\n", "")
        
        if len(err) > 0:
            raise Exception(err)

        logger.debug(" - add code: %s" % ps.returncode) 
        
        return ([ps], out, err)

class FreshBeats(object):

    ''' Fresher beats '''

    device_mount = None
    dev = None

    def __init__(self):

        self.bytes_free = 0
        self.fail = 0

        config = ConfigParser()
        config.read(
            join(os.path.dirname(__file__), './config/settings.cfg')
        )

        for section in config.sections():
            if section == 'process':
                self.process = Process(**{ i[0]: i[1] for i in config.items(section) })
            else:
                for i in config.items(section):
                    self.__setattr__(i[0], i[1])
                
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

            tup = folder_path.split(b'/')

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

            max_album = max([ len(a.name) for a in found_on_device ]) + 1
            max_artist = max([ len(a.artist.name) for a in found_on_device ]) + 1

            logger.info("Albums on Device")
            logger.debug(max_album)
            logger.debug(max_artist)
            
            for a in found_on_device:
                checked_out = a.current_albumcheckout() is not None
                # logger.debug(a.name)
                
                # logger.debug(a.artist.name)
                
                # logger.debug(a.action)
                # logger.debug("{0:<{1}}".format(a.name, max_album))
                logger.info("{0:<{1}} {2:<{3}} {4} {5}".format(a.name, max_album, a.artist.name, max_artist, a.action if a.action else "<no action>", "checked-out" if checked_out else "not checked out"))

        action_albums = Album.objects.filter(~Q(action=Album.DONOTHING), action__isnull=False)
        if len(action_albums) > 0:
            max_album = max([ len(a.name) for a in action_albums ]) + 1
            max_artist = max([ len(a.artist.name) for a in action_albums ]) + 1
        checkout_size = sum([ a.total_size for a in action_albums.filter(Q(action=Album.CHECKOUT) | Q(action=Album.REQUESTCHECKOUT)) ])
        refresh_size = sum([ a.total_size - a.old_total_size for a in action_albums.filter(Q(action=Album.REFRESH)) ])
        checkin_size = sum([ a.total_size for a in action_albums.filter(action=Album.CHECKIN) ])

        logger.info("Albums in Plan")
        for a in action_albums:
            logger.info(type(a.name))
            logger.info("{0:<{1}} / {2:<{3}}: {4:>32}".format(a.name, max_album, a.artist.name, max_artist, a.action if a.action else '-no action-'))

        logger.info("Checking out {0} MB".format(checkout_size/(1024*1024)))
        logger.info("Refreshing {0} MB".format(refresh_size/(1024*1024)))
        logger.info("Checking in {0} MB".format(checkin_size/(1024*1024)))
        net = checkout_size + refresh_size - checkin_size
        direction = "out" if net >= 0 else "in"
        logger.info("Net: {0} MB {1}".format(abs(net)/(1024*1024), direction))

    # - DEVICE

    def remove_album_from_device(self, a):

        logger.info("removing: %s %s" %(a.artist.name, a.name))
        
        album_path = join(self.beats_target_folder, a.artist.name, a.name)
        command = r'rm -rf \"%s\"' % album_path
        (plist, outs, errs) = self.process.remote_command(command)
        
        logger.info("Remove code: %s" % plist[-1].returncode)

        if plist[-1].returncode == 0:
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

        artist_folder = join(self.beats_target_folder, a.artist.name) #join(self.device_mount, self.beats_target_folder, a.artist)

        logger.info(" - adding folder: \"%s\"" %(artist_folder))
        
        (plist, outs, errs) = self.process.remote_command(r'mkdir -p \"%s\"' % artist_folder)        

        storage_path = join(self.music_path, common.get_storage_path(a))
        logger.debug(" - storage path: %s" % storage_path)

        modified_artist_folder = artist_folder.replace(' ', r'\ ').replace("'", r'\'').replace("&", r'\&')
        logger.debug(" - modified artist folder: %s" % modified_artist_folder)

        (plist, outs, errs) = self.process.copy(storage_path, modified_artist_folder)
        
        if plist[-1].returncode == 0:
            ac = AlbumCheckout(album=a, checkout_at=timezone.now())
            ac.save()
            a.action = None
            a.save()

    def get_music_folders_on_device(self, target_folder):
        
        (plist, outs, errs) = self.process.remote_command(r'find \"%s\" -type d' %(target_folder))
        logger.debug(target_folder)
        logger.debug(outs[-1].split(b'\n'))
        folders = [ f.replace(b'%b/' % bytes(target_folder, encoding='utf8'), b'') for f in outs[-1].split(b'\n') if f and f != target_folder ]

        return folders

    def is_album_on_device(self, album):

        artist_folder = join(self.beats_target_folder, album.artist.name, album.name)

        (plist, outs, errs) = self.process.remote_command([r'find \"%s\"' %(artist_folder), r'wc -l'])

        return int(outs[-1]) > 1

    def get_free_bytes(self):

        #ps = subprocess.Popen('df -k'.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        #ps = subprocess.Popen(('grep ' + self.device_mount).split(' '), stdin=ps.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        (plist, outs, errs) = self.process.remote_command(['df', 'grep emulated'])

        if not outs[-1] and not errs[-1]:
            raise Exception("no out or err in get_free_bytes!")

        # - Filesystem               Size     Used     Free   Blksize
        # - /mnt/shell/emulated     12G     8.5G     3.5G   4096
        for i, out in enumerate(outs):
            logger.debug("%s: %s" % (i, out))
        parts = [p for p in str(outs[-1]).split(' ') if p != '']
        free = parts[3]

        match = re.search(r'([0-9\.]+)([A-Z])', str(free))

        size = match.group(1)
        unit = match.group(2)

        unit_multiplier = {'G': math.pow(1024, 3), 'M': math.pow(1024, 2), 'K': math.pow(1024, 1)}

        size_in_bytes = int(math.floor(float(size)*unit_multiplier[unit]))

        logger.debug("free space: %s MB (%s bytes)" % (int(math.floor(float(size_in_bytes)/unit_multiplier['M'])), size_in_bytes))

        return size_in_bytes

    # - END DEVICE

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

@click.command()
@click.option('--report', '-r', is_flag=True, help='Report on device status and copy plan.')
@click.option('--validate_plan', '-v', is_flag=True, help='Validates album copy plan.')
@click.option('--apply_plan', '-a', is_flag=True, help='Apply copy plan to device.')
@click.option('--new_randoms', '-n', is_flag=True, help='Try to fit new random albums during "apply".')
@click.option('--free', '-f', is_flag=True, help='Show device free information.')
def main(report, validate_plan, apply_plan, new_randoms, free):

    try:

        f = FreshBeats()

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
