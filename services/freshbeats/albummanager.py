import sys
import os
import logging

logger = logging.getLogger()

sys.path.append(os.path.join(os.path.dirname(__file__), '../../webapp'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_env")

import config.settings
import django
from django.db.models import Q
django.setup()

from beater.models import Artist, Album, Song, AlbumCheckout, AlbumStatus

class AlbumManager:

    '''Albums are marked as 'request checkout', 'checkin', or 'refresh'. This class tallys free space for these proposed actions
    and makes adjustments as necessary: upgrade 'request checkout' to 'checkout', downgrade 'refresh' to 'donothing'.'''
    
    free_bytes_margin = None 
    device_free_bytes = None 
    mobile = None 

    def __init__(self, *args, **kwargs):

        # - everything in Bytes
        self.free_bytes_margin = int(kwargs['free_space_margin_mb'])*1024*1024
        self.device_free_bytes = int(kwargs['device_free_bytes'])
        self.mobile = kwargs['mobile']
        
    def _initialize_tallys(self):
        # -- this is maintained for available space calculation
        self.checkout_delta = 0

        # -- these are maintained only for reporting
        self.albums_to_checkin = []
        self.albums_to_refresh = []
        self.albums_to_checkout = []

    def validate_plan(self):
        '''Reads the database, ensures the plan will work, and populates action lists. Proposed album check-outs are "made", if appropriate.'''

        self._initialize_tallys()
        
        db_albums_to_check_in = [ ac.album for ac in self.mobile.albumcheckout_set.filter(next_state=AlbumCheckout.CHECKEDIN) ]
        # db_albums_to_check_in = Album.objects.filter(action=Album.CHECKIN)
        logger.info("Registering %s previously marked albums to check-in.." % len(db_albums_to_check_in))
        self.checkin_albums(db_albums_to_check_in)

        self.send_tallys_to_logger()

        db_albums_to_check_out = [ ac.album for ac in self.mobile.albumcheckout_set.filter(state=AlbumCheckout.VALIDATED, album__sticky=False).order_by('request_priority') ]
        # db_albums_to_check_out = Album.objects.filter(action=Album.CHECKOUT,
        #                                               sticky=False).order_by('request_priority')
        logger.info("Re-validating %s previously marked albums to check-out.."
                    % len(db_albums_to_check_out))
        for album in db_albums_to_check_out:
            if not self.validate_checkout_album(album):
                logger.warn("   Rejected checkout of %s/%s (%s MB free/%s MB margin)"
                            % (album.artist.name, album.name,
                                (self.real_available_bytes() - album.total_size)/(1024*1024),
                                self.free_bytes_margin/(1024*1024)))

        self.send_tallys_to_logger()
        
        db_requested_albums_to_check_out = [ ac.album for ac in self.mobile.albumcheckout_set.filter(state=AlbumCheckout.REQUESTED, album__sticky=False) ]
        # db_requested_albums_to_check_out = Album.objects.filter(action=Album.REQUESTCHECKOUT, sticky=False)
        logger.info("Validating %s previously requested albums to check-out.." % len(db_requested_albums_to_check_out))
        for album in db_requested_albums_to_check_out:
            if not self.validate_checkout_album(album):
                logger.warn("   Rejected checkout of %s/%s (%s MB free/%s MB margin)"
                            % (album.artist.name, album.name,
                                (self.real_available_bytes() - album.total_size)/(1024*1024),
                                self.free_bytes_margin/(1024*1024)))

        self.send_tallys_to_logger()
        
        db_albums_to_refresh = [ ac.album for ac in self.mobile.albumcheckout_set.filter(next_state=AlbumCheckout.REFRESH) ]
        # db_albums_to_refresh = Album.objects.filter(action=Album.REFRESH)
        logger.info("Validating %s previously marked albums to refresh.." % len(db_albums_to_refresh))
        for album in db_albums_to_refresh:
            if not self.validate_refresh_album(album):
                delta = album.total_size - album.old_total_size
                logger.warn("   Rejected refresh of %s/%s (%s MB free/%s MB margin)"
                            % (album.artist.name, album.name,
                                (self.real_available_bytes() - delta)/(1024*1024),
                                self.free_bytes_margin/(1024*1024)))

        self.send_tallys_to_logger()
        self.send_status_to_logger()

    def send_tallys_to_logger(self):
        logger.info("%s out, %s in, %s MB delta => %s MB free" % (
            len(self.albums_to_checkin),
            len(self.albums_to_checkout),
            self.checkout_delta/(1024*1024),
            self.real_available_bytes()/(1024*1024)
        ))

    def send_status_to_logger(self):

        logger.info("-- Device Current Status -- ")
        logger.info(" Device Free: {0:>10}".format(self.device_free_bytes))
        logger.info(" Free Margin: {0:>10}".format(self.free_bytes_margin))
        logger.info("-- Plan Result -- ")
        logger.info(" Checking-in: {0:>10}".format(sum([ a.total_size for a in self.albums_to_checkin ])))
        logger.info("  Refreshing: {0:>10}".format(sum([ a.total_size - a.old_total_size for a in self.albums_to_refresh ])))
        logger.info("Checking-out: {0:>10}".format(sum([ a.total_size for a in self.albums_to_checkout ])))
        logger.info("  Plan Delta: {0:>10}".format(self.checkout_delta))
        logger.info(" Device Free: {0:>10}".format(self.real_available_bytes()))

    def plan_available_bytes(self):
        '''Zero-floored available bytes accounting for the current checkout tally per validation, CONSIDERING the desired free space margin'''

        avail = self.device_free_bytes - self.free_bytes_margin - self.checkout_delta

        if avail > 0:
            return avail

        return 0

    def real_available_bytes(self):
        '''Available bytes accounting for the current checkout tally per validation, NOT considering the desired free space margin'''

        real_avail = self.device_free_bytes - self.checkout_delta

        return real_avail

    def checkin_albums(self, albums):
        '''Marks an album as 'checkin, managing album list and checkout_delta.'''

        for album in albums:

            # -- this action is probably already set, the purpose here is more to tally free space
            #album.action = Album.CHECKIN
            #album.save()

            self.albums_to_checkin.append(album)
            self.checkout_delta -= album.total_size

    def validate_refresh_album(self, album):
        '''Moves an album from 'refresh' to 'donothing' if the space delta is too large, managing album list and checkout_delta.'''
        valid = False

        delta = album.total_size - album.old_total_size

        logger.debug("Delta is %s, available = %s" % (delta, self.plan_available_bytes()))

        if self.plan_available_bytes() < delta:

            album.action = Album.DONOTHING
            album.save()
        else:
            self.albums_to_refresh.append(album)
            self.checkout_delta += delta
            valid = True

        return valid

    def validate_checkout_album(self, album):
        '''
        Upgrades an album from 'request checkout' to 'checkout' if space allows, managing album list and checkout_delta.
        '''

        valid = False
        checkout = album.current_albumcheckout(self.mobile.id)
        if not checkout:
            raise Exception(f'Album {album.name} doesn\'t have a current checkout.. should not be validating')
            
        if self.plan_available_bytes() >= album.total_size:
            self.albums_to_checkout.append(album)
            self.checkout_delta += album.total_size
            checkout.state = AlbumCheckout.VALIDATED 
            checkout.save()
            # if album.action == Album.REQUESTCHECKOUT:
            #     album.action = Album.CHECKOUT
            #     album.save()
            valid = True
        else:
            checkout.state = AlbumCheckout.REQUESTED
            checkout.save()
            # if album.action == Album.CHECKOUT:
            #     album.action = Album.REQUESTCHECKOUT
            #     album.save()

        return valid

    def checkout_album(self, album):
        '''Validates a checkout and marks an album directly for 'checkout' for random and mixin additions.'''

        valid = False

        if self.validate_checkout_album(album):

            if album.action != Album.REQUESTCHECKOUT and not album.sticky:
                album.request_priority = 2

            album.action = Album.CHECKOUT
            album.save()

            valid = True
        else:
            pass

        return valid
