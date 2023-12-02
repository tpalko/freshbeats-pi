#!/usr/bin/env python

import os
import sys
from os.path import join
import subprocess
import shlex
import logging
import random
import traceback
import datetime
from configparser import ConfigParser
import re
import math
# from .device import DeviceManager
try:
    from albummanager import AlbumManager
except ImportError as e:
    from .albummanager import AlbumManager
import click

# import config.settings_env

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

from beater.models import Artist, Album, Song, AlbumCheckout, AlbumStatus, Mobile

django.setup()

logger = logging.getLogger('freshbeats.freshbeats')

# logger.setLevel(logging.INFO)

# DJANGO_LOGGER = logging.getLogger('django')
# DJANGO_LOGGER.setLevel(logging.INFO)
# REQUESTS_LOGGER = logging.getLogger('requests')
# REQUESTS_LOGGER.setLevel(logging.INFO)
# URLLIB3_LOGGER = logging.getLogger('urllib3')
# URLLIB3_LOGGER.setLevel(logging.WARN)

# name_logger = logging.getLogger(__name__)

class Process(object):
    
    web_user = None 
    
    name = None 
    ip_address = None 
    ssh_username = None 
    ssh_private_key_path = None 
    target_path = None 
    
    def __init__(self, *args, **kwargs):
        for key in kwargs.keys():
            logger.debug("setting %s <= %s" % (key, kwargs[key]))
            self.__setattr__(key, kwargs[key])

    def _whoami(self):
        (plist, outs, errs) = self.auto_command('whoami')
        return outs[0]
        
    def _get_ssh_identity_file_parameter(self):

        user = self._whoami()
        logger.debug("acting user: %s" % user)

        ssh_parameters = ''
        
        #logger.debug("web_user: %s" % self.web_user)
        if user == self.web_user and self.ssh_private_key_path:
            ssh_parameters = f'-i {self.ssh_private_key_path} -o StrictHostKeyChecking=no'
        
        address = f'{self.ssh_username}@{self.ip_address}'
        
        #logger.debug("parameters: %s" % ssh_parameters)
        #logger.debug("address: %s" % address)
        
        return (ssh_parameters, address)
    
    def get_free_bytes(self):
        
        #ps = subprocess.Popen('df -k'.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        #ps = subprocess.Popen(('grep ' + self.device_mount).split(' '), stdin=ps.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        (plist, outs, errs) = self.auto_command([f'df {self.target_path}', 'grep -v Filesystem'])
        
        # if not outs[-1] and not errs[-1]:
        #     raise Exception(f'no out {outs} or err {errs} in get_free_bytes!')
        
        logger.debug(outs)
        # - Filesystem               Size     Used     Free   Blksize
        # - /mnt/shell/emulated     12G     8.5G     3.5G   4096
        # for i, out in enumerate(outs):
        #     logger.debug("%s: %s" % (i, out))
        parts = [p for p in str(outs[0]).split(' ') if p != '']
        logger.debug(parts)
        
        free = parts[3]
        
        num_match = '([0-9]+)'
        match = re.search(num_match, str(free))
        
        if not match:
            raise ValueError(f'No match of {num_match} was found in "{free}" (full string: {parts})')
        
        size = match.group(1)
        unit = 'K'
        
        unit_multiplier = {'G': math.pow(1024, 3), 'M': math.pow(1024, 2), 'K': math.pow(1024, 1), 'B': 1}

        size_in_bytes = int(math.floor(float(size)*unit_multiplier[unit]))

        logger.debug("free space: %s MB (%s bytes)" % (int(math.floor(float(size_in_bytes)/unit_multiplier['M'])), size_in_bytes))

        return size_in_bytes
        
    def remove_album(self, artist_name, album_name):
        album_path = join(self.target_path, artist_name, album_name)
        command = r'rm -rf "%s"' % album_path
        return self.auto_command(command)
        
    def add_album(self, storage_path, artist_name):
        
        user = self._whoami()
        logger.debug("acting user: %s" % user)
        
        artist_folder = join(self.target_path, artist_name)
        logger.info(" - adding folder: \"%s\"" %(artist_folder))
        
        (plist, outs, errs) = self.auto_command(r'mkdir -p "%s"' % artist_folder)        

        modified_artist_folder = artist_folder #.replace(' ', r'\ ').replace("'", r'\'').replace("&", r'\&')
        logger.debug(" - modified artist folder: %s" % modified_artist_folder)

        return self._copy_album(storage_path, modified_artist_folder)
    
    def get_music_folders_on_device(self):
        logger.info("Report on device folder '%s'", self.target_path)
        (plist, outs, errs) = self.auto_command('find \"%s\" -type d' %(self.target_path))
        logger.debug(outs[-1].split(b'\n'))
        return [ f.replace(b'%b/' % bytes(self.target_path, encoding='utf8'), b'') for f in outs[-1].split(b'\n') if f and f != self.target_path ]
    
    def is_album_on_device(self, artist_name, album_name):
        artist_folder = join(self.target_path, artist_name, album_name)
        (plist, outs, errs) = self.auto_command([r'find \"%s\"' %(artist_folder), r'wc -l'])
        return int(outs[-1]) > 1

    def _get_executable_statement(self, command, force_local=False):
        
        if self.ip_address and not force_local:
            (parameters, address) = self._get_ssh_identity_file_parameter()
            return shlex.split(r'ssh %s %s "%s"' %(parameters, address, command))
        else:
            return shlex.split(command)
    
    def _get_copy_statement(self, file, path):
        
        if self.ip_address:
            (parameters, address) = self._get_ssh_identity_file_parameter()
            return shlex.split(r'scp -r %s "%s" %s:"%s/"' % (parameters, file, address, path))
        else:
            return shlex.split(r'cp -an "%s" "%s/"' % (file, path))
            
    def auto_command(self, commands):
        
        if type(commands) == str:
            commands = [commands]
        
        plist = []
        outs = []
        errs = []
        
        for i, command in enumerate(commands, 1):
            
            statement = self._get_executable_statement(command, force_local=(i < len(commands)))
            
            logger.info(f'filing {command}')
            plist.append({
                'command': command,
                'ps': subprocess.Popen(statement, stdin=plist[-1]['ps'].stdout if len(plist) > 0 else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            })
        
        plist.reverse()
        
        for p in plist:
            logger.info(f'communicate: "{p["command"]}"')
            (out, err) = p['ps'].communicate(None)
            logger.debug("out: %s" % out)
            logger.debug("err: %s" % err)
            outs.append(out)
            errs.append(err)
       
        return plist, outs, errs
    
    def _copy_album(self, file, path):
        
        cp_statement = self._get_copy_statement(file, path)
        logger.debug(" - %s" % cp_statement)

        ps = {
            'ps': subprocess.Popen(cp_statement, stdout=subprocess.PIPE, stderr=subprocess.PIPE),
            'command': cp_statement
        }
        
        (out,err,) = ps['ps'].communicate(None)

        err = err.decode().replace("void endpwent()(3) is not implemented on Android\n", "")
        
        if len(err) > 0:
            raise Exception(err)

        logger.debug(" - add code: %s" % ps['ps'].returncode) 
        
        return ([ps], out, err)

class FreshBeats(object):

    ''' Fresher beats '''

    device_mount = None
    dev = None
    mobile = None 
    
    music_path = None 
    free_space_margin_mb = None 
    
    def __init__(self, *args, **kwargs):
        
        try:
                
            if 'mobile_id' not in kwargs:
                raise Exception("mobile_id missing")
            
            self.mobile = Mobile.objects.get(pk=kwargs['mobile_id'])
            
            self.process = Process(**{ f.name: self.mobile.__dict__[f.name] for f in self.mobile._meta.fields })
            
            self.bytes_free = 0
            self.fail = 0

            config = ConfigParser()
            config.read(
                join(os.path.dirname(__file__), './config/settings.cfg')
            )

            # self.process = Process(**{ i[0]: i[1] for i in config.items(section) })
            for section in config.sections():
                if section == 'albummanager':
                    self.album_manager = AlbumManager(**{**{ i[0]: i[1] for i in config.items(section) }, 'device_free_bytes': self.get_free_bytes(), 'mobile': self.mobile})
                else:
                    for i in config.items(section):
                        self.__setattr__(i[0], i[1])
                    
            # self.device = DeviceManager(hostname=self.device_hostname,
            # username=self.ssh_username, target_folder=self.beats_target_folder)
            # self.album_manager = None

            if os.getenv('FRESHBEATS_MUSIC_PATH'):
                self.music_path = os.getenv('FRESHBEATS_MUSIC_PATH')

            if not os.path.exists(self.music_path):
                logger.error("Music path %s does not exist. Exiting.", self.music_path)
                exit(1) 
        except Exception as e:
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
            raise e
    
    def get_free_bytes(self):
        return self.process.get_free_bytes()
        
    def plan_report(self):

        folders_on_device = self.process.get_music_folders_on_device()

        found_on_device = []
        found_on_device_no_subfolder = []

        for folder_path in folders_on_device:
            
            folder_path = folder_path.decode('utf-8')
            
            logger.debug("Folder found: %s" % folder_path)

            tup = folder_path.split('/')

            if len(tup) < 2:
                logger.debug(f'No subfolder for {folder_path}')
                found_on_device_no_subfolder.append(folder_path)
                continue

            artist = tup[-2]
            album = tup[-1]
            
            logger.debug(f'Looking up artist {artist}')
            artist_matches = Artist.objects.filter(name=artist)

            if len(artist_matches) > 0:
                logger.debug("Found %s artists for '%s'" % (len(artist_matches), artist))

            for artist_match in artist_matches:
                logger.debug(f'Attempting to match album {album} to artist {artist_match.name}')
                album_match = Album.objects.filter(artist__name=artist_match.name, name=album).first()
                if album_match:
                    logger.debug(f'Found album {album_match.name}')
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
            # logger.debug(max_album)
            # logger.debug(max_artist)
            
            for a in found_on_device:
                current_checkout = a.current_albumcheckout(self.mobile.id)
                state = "no checkout"
                next_state = "no checkout"
                if current_checkout:
                    state = current_checkout.state
                    next_state = current_checkout.next_state or "no next state on checkout"
                
                # logger.debug(a.name)
                
                # logger.debug(a.artist.name)
                
                # logger.debug(a.action)
                # logger.debug("{0:<{1}}".format(a.name, max_album))
                
                logger.info("{0:<{1}} {2:<{3}} {4} {5}".format(a.name, max_album, a.artist.name, max_artist, state, next_state))

        mobile_albumcheckouts = self.mobile.albumcheckout_set.filter(~Q(state=AlbumCheckout.CHECKEDIN))
        if len(mobile_albumcheckouts) > 0:
            max_album = max([ len(ac.album.name) for ac in mobile_albumcheckouts ]) + 1
            max_artist = max([ len(ac.album.artist.name) for ac in mobile_albumcheckouts ]) + 1
        checkout_size = sum([ ac.album.total_size for ac in mobile_albumcheckouts.filter(Q(state=AlbumCheckout.REQUESTED) | Q(state=AlbumCheckout.VALIDATED)) ])
        refresh_size = sum([ ac.album.total_size - ac.album.old_total_size for ac in mobile_albumcheckouts.filter(Q(state=AlbumCheckout.REFRESH)) ])
        checkin_size = sum([ ac.album.total_size for ac in mobile_albumcheckouts.filter(state=AlbumCheckout.CHECKEDOUT, next_state=AlbumCheckout.CHECKEDIN) ])

        logger.info("Albums in Plan")
        for ac in mobile_albumcheckouts:
            logger.info(type(ac.album.name))
            logger.info("{0:<{1}} / {2:<{3}}: {4:<12}/{5:>32}".format(ac.album.name, max_album, ac.album.artist.name, max_artist, ac.state, ac.next_state or '-'))

        logger.info("Checking out {0} MB".format(checkout_size/(1024*1024)))
        logger.info("Refreshing {0} MB".format(refresh_size/(1024*1024)))
        logger.info("Checking in {0} MB".format(checkin_size/(1024*1024)))
        net = checkout_size + refresh_size - checkin_size
        direction = "out" if net >= 0 else "in"
        logger.info("Net: {0} MB {1}".format(abs(net)/(1024*1024), direction))

    # - DEVICE

    def remove_album_from_device(self, a):

        logger.info("removing: %s %s" %(a.artist.name, a.name))
        (plist, outs, errs) = self.process.remove_album(a.artist.name, a.name)
        
        logger.info("Remove code: %s" % plist[-1]['ps'].returncode)

        if plist[-1]['ps'].returncode == 0:
            current_checkout = a.current_albumcheckout(self.mobile.id)
            if current_checkout:
                while current_checkout is not None:
                    current_checkout.return_at = timezone.now()
                    current_checkout.state = AlbumCheckout.CHECKEDIN
                    current_checkout.next_state = None 
                    current_checkout.save()
                    current_checkout = a.current_albumcheckout(self.mobile.id)
                    if current_checkout:
                        logger.warn("%s/%s checked out multiple times!" % (a.artist.name, a.name))
            else:
                logger.warn("removing from device, but not checked out!")
            a.action = None
            a.save()

    def copy_album_to_device(self, a):
        
        storage_path = join(self.music_path, common.get_storage_path(a))
        logger.debug(" - storage path: %s" % storage_path)
        
        (plist, outs, errs) = self.process.add_album(storage_path, a.artist.name)
        
        if plist[-1]['ps'].returncode == 0:
            checkout = a.current_albumcheckout(self.mobile)
            checkout.state = AlbumCheckout.CHECKEDOUT 
            checkout.checkout_at = timezone.now()
            checkout.save()
    
    # - END DEVICE
        
    def _pick_random_fill_albums(self):

        # - we want to keep at least one mix-it-up-rated album
        # - if we aren't renewing one, pick one to check out
        # any_kept_mixins = Album.objects.filter(Q(rating=Album.MIXITUP) & Q(albumcheckout__isnull=False) & Q(albumcheckout__return_at__isnull=True) & Q(albumcheckout__mobile=self.mobile)).exists()
        any_kept_mixings = self.mobile.albumcheckout_set.filter(return_at__isnull=True, album__rating=Album.MIXITUP).exists()
        if not any_kept_mixins:

            # -- albums where 
            # -- rating is mixitiup
            # -- AND 
            # -- there are no albumcheckout records a) for my mobile AND b) NOT checked-in
            new_mixins = Album.objects.filter(~(Q(albumcheckout__mobile=self.mobile) & ~Q(albumcheckout__state=AlbumCheckout.CHECKEDIN)), rating=Album.MIXITUP)
            new_mixin_list = list(new_mixins)

            if len(new_mixin_list) > 0:
                new_mixin = random.choice(new_mixin_list)
                logger.info("Registering a mix-it-up album...")
                if not self.album_manager.checkout_album(new_mixin):
                    logger.warn("Rejected checkout of %s/%s" % (new_mixin.artist.name, new_mixin.name))

        loveit_albums = Album.objects.filter(rating=Album.LOVEIT, action=None)
        # -- albums where 
        # -- no albumcheckout records at all 
        # -- OR 
        # -- any albumcheckout records are not my mobile 
        never_checked_out_albums = Album.objects.filter(Q(albumcheckout__isnull=True) | ~Q(albumcheckout__mobile=self.mobile))
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
        self.album_manager.validate_plan()

    def apply_plan(self, new_randoms=True):

        try:

            self.validate_plan()

            if new_randoms:
                self._pick_random_fill_albums()

            remove_albums = [ ac.album for ac in self.mobile.albumcheckout_set.filter(next_state=AlbumCheckout.CHECKEDIN) ]
            # remove_albums = Album.objects.filter(action=Album.CHECKIN)

            for r in remove_albums:
                self.remove_album_from_device(r)
            
            refresh_albums = [ ac.album for ac in self.mobile.albumcheckout_set.filter(next_state=AlbumCheckout.REFRESH) ]
            # refresh_albums = Album.objects.filter(action=Album.REFRESH)

            for u in refresh_albums:
                self.remove_album_from_device(u)
                self.copy_album_to_device(u)
            
            sticky_albums = [ ac.album for ac in self.mobile.albumcheckout_set.filter(album__sticky=True) ]
            # sticky_albums = Album.objects.filter(sticky=True)

            for s in sticky_albums:
                #self.remove_album_from_device(s)
                if not self.process.is_album_on_device(s.artist.name, s.name):
                    logger.info("Sticky album %s missing" % s)
                    self.copy_album_to_device(s)
                else:
                    logger.info("Sticky album %s already present, moving on.." % s)
            
            add_albums = [ ac.album for ac in self.mobile.albumcheckout_set.filter(state=AlbumCheckout.VALIDATED) ]
            # add_albums = Album.objects.filter(action=Album.CHECKOUT)

            for a in add_albums:
                self.copy_album_to_device(a)
            # 
            # nothing_albums = Album.objects.filter(action=Album.DONOTHING)
            # 
            # for a in nothing_albums:
            #     a.action = None
            #     a.save()
        except:
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])

@click.command()
@click.argument('mobile_id')
@click.option('--report', '-r', is_flag=True, help='Report on device status and copy plan.')
@click.option('--validate_plan', '-v', is_flag=True, help='Validates album copy plan.')
@click.option('--apply_plan', '-a', is_flag=True, help='Apply copy plan to device.')
@click.option('--new_randoms', '-n', is_flag=True, help='Try to fit new random albums during "apply".')
@click.option('--free', '-f', is_flag=True, help='Show device free information.')
def main(mobile_id, report, validate_plan, apply_plan, new_randoms, free):

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
            logger.info(f.get_free_bytes())

    except:
        logger.error(sys.exc_info()[0])
        logger.error(sys.exc_info()[1])
        traceback.print_tb(sys.exc_info()[2])

if __name__ == "__main__":
    main()
