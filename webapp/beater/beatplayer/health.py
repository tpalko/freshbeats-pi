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
    
    __instances = {} 
    lock = None 
    
    @staticmethod
    def getInstance(agent_base_url=None):
        if not agent_base_url:
            logger.info("BeatplayerRegistrar instance requested with no agent base URL, using settings value '%s'" % settings.BEATPLAYER_URL)
            agent_base_url = settings.BEATPLAYER_URL
        if agent_base_url not in BeatplayerRegistrar.__instances or BeatplayerRegistrar.__instances[agent_base_url] == None:
            BeatplayerRegistrar(agent_base_url=agent_base_url)
        return BeatplayerRegistrar.__instances[agent_base_url] 
        
    def __init__(self, *args, **kwargs):
        if kwargs['agent_base_url'] in BeatplayerRegistrar.__instances and BeatplayerRegistrar.__instances[kwargs['agent_base_url']] != None:
            raise Exception("Singleton instance exists!")
        else:
            self.lock = threading.Lock()
            BeatplayerRegistrar.__instances[kwargs['agent_base_url']] = self 
    
    def _get_device(self, agent_base_url=None):
        if not agent_base_url:
            logger.info("Client state requested with no agent base URL, using settings value '%s'" % settings.BEATPLAYER_URL)
            agent_base_url = settings.BEATPLAYER_URL 
        device = Device.objects.filter(agent_base_url=agent_base_url).first()
        if not device:
            logger.info("No device was found with agent_base_url '%s'" % agent_base_url)
            device = Device(agent_base_url=agent_base_url)
        return device
        
    @contextmanager
    def device(self, agent_base_url=None, read_only=False):
        if read_only:                        
            device = self._get_device(agent_base_url=agent_base_url)
            #logger.debug("Client state (r/o yield): %s" % device.status_dump())
            try:
                yield device
            finally:
                pass 
        else:        
            logger.debug("Client state R/W request")    
            caller = traceback.format_stack()[-3].split(' ')[7].replace('\n', '')
            logger.debug("%s wants to acquire client record lock.." % caller)
            self.lock.acquire()
            logger.debug("%s has acquired client record lock" % caller)
            device = self._get_device(agent_base_url=agent_base_url)
            logger.debug("Client state (yield): %s" % device.status_dump())
            try:
                yield device
            except:
                logger.error(sys.exc_info()[1])
            finally:
                self._set_and_show_status(device)
                logger.debug("Client state (save): %s" % device.status_dump())
                device.save()
                self.lock.release()
    
    def log_health_response(self, health_data):
        with self.device(agent_base_url=health_data['agent_base_url']) as device:
            now = get_localized_now()            
            device.mounted = health_data['music_folder_mounted']
            device.last_health_check = now

    def _set_and_show_status(self, device):
        if device.reachable and device.registered and device.selfreport and device.mounted:
            device.status = Device.DEVICE_STATUS_READY
        elif not device.reachable:
            device.status = Device.DEVICE_STATUS_DOWN
        else:
            device.status = Device.DEVICE_STATUS_NOTREADY
        self._show_beatplayer_status(device.status_dump())
    
    def _show_beatplayer_status(self, beatplayer_status):
        _publish_event('beatplayer_status', beatplayer_status)
        
    def show_status(self):
        with self.device(read_only=True) as device:
            self._show_beatplayer_status(device.status_dump())
        
    def register(self):
        def register_client():
            attempts = 0
            while True:
                with self.device() as device:
                    logger.info("Attempting to register at %s with %s" % (device.agent_base_url, settings.FRESHBEATS_CALLBACK_URL))
                    try:
                        attempts += 1
                        beatplayer_client = client.ServerProxy(device.agent_base_url)
                        response = beatplayer_client.register_client(settings.FRESHBEATS_CALLBACK_URL, device.agent_base_url)
                        device.reachable = True 
                        device.registered = response['data']['registered']
                        if device.registered:
                            logger.info("  - application subscribed to beatplayer! (%s attempts)" % attempts)                        
                            device.registered_at = get_localized_now()
                        else:
                            logger.debug("  - attempt %s - not yet registered: %s" % (attempts, response))
                        if response['data']['retry'] == False:
                            logger.info("  - quitting registration loop (registered: %s)" % device.registered)
                            break
                    except ConnectionRefusedError as cre:
                        device.reachable = False 
                    except:
                        logger.error(sys.exc_info()[0])
                        logger.error(sys.exc_info()[1])
                        #traceback.print_tb(sys.exc_info()[2])
                        device.reachable = False 
                        logger.error("Error registering with %s: %s" % (device.agent_base_url, str(sys.exc_info()[1])))
                    if device.registered:
                        logger.info("  - quitting registration loop (registered: %s)" % device.registered)
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
                with self.device() as device:
                    if device.last_health_check is None:
                        misses += 1
                        logger.warn("No beatplayer report: %s/3" % misses)
                        if misses > 2:
                            device.selfreport = False 
                            break 
                    else:
                        since_last = (now - device.last_health_check).total_seconds()
                        logger.debug("Last health check response: %s seconds ago (%s)" % (since_last, datetime.strftime(device.last_health_check, "%Y-%m-%d %H:%M:%S")))
                        misses = 0
                        if since_last > REGISTRATION_TIMEOUT:
                            device.selfreport = False 
                            logger.warn("Beatplayer down for %s seconds, assuming restart, quitting fresh check and attempting re-registration" % (since_last))
                            break
                        elif since_last > 15:
                            device.selfreport = False 
                            logger.warn("Beatplayer down for %s seconds, stale status" % since_last)
                        else:
                            device.selfreport = True 
                time.sleep(5)
            with self.device() as device:
                logger.warn("Self-deregistering..")
                device.registered = False          
            t = threading.Thread(target=register_client)
            t.start()
                    
        t = threading.Thread(target=register_client)
        t.start()
