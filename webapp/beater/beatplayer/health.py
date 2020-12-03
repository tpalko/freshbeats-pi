import sys
import os
import json
import logging
import traceback
import threading
import time
from xmlrpc import client
from datetime import datetime, timedelta
from contextlib import contextmanager 
from django.conf import settings
from ..common.switchboard import _publish_event
from ..common.util import get_localized_now
from ..models import Device

REGISTRATION_TIMEOUT = int(os.getenv('FRESHBEATS_BEATPLAYER_REGISTRATION_TIMEOUT', 30))
REGISTRATION_BACKOFF = int(os.getenv('FRESHBEATS_BEATPLAYER_REGISTRATION_BACKOFF', 3))

logger = logging.getLogger(__name__)

class BeatplayerRegistrar():
    
    __instance = None 
    lock = None 
    
    @staticmethod
    def getInstance():
        if BeatplayerRegistrar.__instance == None:
            BeatplayerRegistrar()
        return BeatplayerRegistrar.__instance 
        
    def __init__(self, *args, **kwargs):
        if BeatplayerRegistrar.__instance != None:
            raise Exception("Singleton instance exists!")
        else:
            self.lock = threading.Lock()
            BeatplayerRegistrar.__instance = self 
    
    def _get_client_state(self):
        client_state = Device.objects.filter(agent_base_url=settings.BEATPLAYER_URL).first()
        if not client_state:
            client_state = Device(agent_base_url=settings.BEATPLAYER_URL)
        return client_state
        
    @contextmanager
    def client_state(self, read_only=False):
        if read_only:                        
            client_state = self._get_client_state()
            #logger.debug("Client state (r/o yield): %s" % client_state.status_dump())
            try:
                yield client_state
            finally:
                pass 
        else:        
            logger.debug("Client state R/W request")    
            caller = traceback.format_stack()[-3].split(' ')[7].replace('\n', '')
            logger.debug("%s wants to acquire client record lock.." % caller)
            self.lock.acquire()
            logger.debug("%s has acquired client record lock" % caller)
            client_state = self._get_client_state()
            logger.debug("Client state (yield): %s" % client_state.status_dump())
            try:
                yield client_state
            finally:
                logger.debug("Client state (save): %s" % client_state.status_dump())
                client_state.save()
                self.lock.release()
    
    def log_health_response(self, health_data):
        with self.client_state() as client_state:
            now = get_localized_now()            
            client_state.mounted = health_data['music_folder_mounted']
            client_state.last_health_check = now
            self._set_and_show_status(client_state)

    def _set_and_show_status(self, client_state):
        if client_state.reachable and client_state.registered and client_state.selfreport and client_state.mounted:
            client_state.status = Device.DEVICE_STATUS_READY
        elif not client_state.reachable:
            client_state.status = Device.DEVICE_STATUS_DOWN
        else:
            client_state.status = Device.DEVICE_STATUS_NOTREADY
        self._show_beatplayer_status(client_state.status_dump())
    
    def _show_beatplayer_status(self, beatplayer_status):
        _publish_event('beatplayer_status', beatplayer_status)
        
    def show_status(self):
        with self.client_state(read_only=True) as client_state:
            self._show_beatplayer_status(client_state.status_dump())
        
    def register(self):
        def register_client():
            attempts = 0
            while True:
                with self.client_state() as client_state:
                    logger.info("Attempting to register at %s with %s" % (client_state.agent_base_url, settings.FRESHBEATS_CALLBACK_URL))
                    try:
                        attempts += 1
                        beatplayer_client = client.ServerProxy(client_state.agent_base_url)
                        response = beatplayer_client.register_client(settings.FRESHBEATS_CALLBACK_URL)
                        client_state.reachable = True 
                        client_state.registered = response['data']['registered']
                        if client_state.registered:
                            logger.info("  - application subscribed to beatplayer! (%s attempts)" % attempts)                        
                            client_state.registered_at = get_localized_now()
                        else:
                            logger.debug("  - attempt %s - not yet registered: %s" % (attempts, response))
                        if response['data']['retry'] == False:
                            logger.info("  - quitting registration loop (registered: %s)" % client_state.registered)
                            break
                    except ConnectionRefusedError as cre:
                        client_state.reachable = False 
                    except:
                        logger.error(sys.exc_info()[0])
                        logger.error(sys.exc_info()[1])
                        #traceback.print_tb(sys.exc_info()[2])
                        client_state.reachable = False 
                        logger.error("Error registering with %s: %s" % (client_state.agent_base_url, str(sys.exc_info()[1])))
                    self._set_and_show_status(client_state)
                    if client_state.registered:
                        logger.info("  - quitting registration loop (registered: %s)" % client_state.registered)
                        break
                    wait = attempts*REGISTRATION_BACKOFF if attempts < 200 else 600
                    logger.debug(" - registration attempt: %s, waiting %s.." % (attempts, wait))
                    time.sleep(wait)
            # - wait a moment after registering to start fresh checking..
            time.sleep(5)
            t = threading.Thread(target=fresh_check)
            t.start()
        def fresh_check():
            misses = 0
            while True:
                now = get_localized_now()
                with self.client_state() as client_state:
                    if client_state.last_health_check is None:
                        misses += 1
                        logger.warn("No beatplayer report: %s/3" % misses)
                        if misses > 2:
                            client_state.selfreport = False 
                            break 
                    else:
                        since_last = (now - client_state.last_health_check).total_seconds()
                        logger.debug("Last health check response: %s seconds ago (%s)" % (since_last, datetime.strftime(client_state.last_health_check, "%Y-%m-%d %H:%M:%S")))
                        misses = 0
                        if since_last > REGISTRATION_TIMEOUT:
                            client_state.selfreport = False 
                            logger.warn("Beatplayer down for %s seconds, assuming restart, quitting fresh check and attempting re-registration" % (since_last))
                            break
                        elif since_last > 15:
                            client_state.selfreport = False 
                            logger.warn("Beatplayer down for %s seconds, stale status" % since_last)
                        else:
                            client_state.selfreport = True 
                    self._set_and_show_status(client_state)
                time.sleep(5)
            with self.client_state() as client_state:
                logger.warn("Self-deregistering..")
                client_state.registered = False          
                self._set_and_show_status(client_state)
            t = threading.Thread(target=register_client)
            t.start()
                    
        t = threading.Thread(target=register_client)
        t.start()
