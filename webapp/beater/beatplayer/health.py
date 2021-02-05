import base64
import sys
import requests
import os
import json
import logging
import traceback
import threading
from urllib import parse 
import time
from xmlrpc import client
from datetime import datetime, timedelta
from contextlib import contextmanager 
from django.conf import settings
from django.db.models import Q
from django.contrib.sessions.backends.db import SessionStore 
from django.contrib.sessions.models import Session 
from django.urls import reverse
from ..common.switchboard import _publish_event, _get_switchboard_connection_id_for_device_id
from ..common.util import get_localized_now
from ..models import Device

REGISTRATION_TIMEOUT = int(os.getenv('FRESHBEATS_BEATPLAYER_REGISTRATION_TIMEOUT', 30))
REGISTRATION_BACKOFF = int(os.getenv('FRESHBEATS_BEATPLAYER_REGISTRATION_BACKOFF', 3))
MAX_REGISTRATION_ATTEMPTS = int(os.getenv('FRESHBEATS_BEATPLAYER_MAX_REGISTRATION_ATTEMPTS', 5))
HEALTH_LOOP_MAX_ITERATIONS = int(os.getenv('FRESHBEATS_BEATPLAYER_HEALTH_LOOP_MAX_ITERATIONS', 30))

logger = logging.getLogger(__name__)

class BeatplayerRegistrar():
    
    __instances = {} 
    agent_base_url = None 
    lock = None 
    health_loop_thread = None 
    
    @staticmethod
    def getInstance(agent_base_url):
        # if not agent_base_url:
        #     logger.info("BeatplayerRegistrar instance requested with no agent base URL, using settings value '%s'" % settings.BEATPLAYER_URL)
        #     agent_base_url = settings.BEATPLAYER_URL
        if agent_base_url not in BeatplayerRegistrar.__instances or BeatplayerRegistrar.__instances[agent_base_url] == None:
            BeatplayerRegistrar(agent_base_url=agent_base_url)
        return BeatplayerRegistrar.__instances[agent_base_url] 
        
    def __init__(self, *args, **kwargs):
        if kwargs['agent_base_url'] in BeatplayerRegistrar.__instances and BeatplayerRegistrar.__instances[kwargs['agent_base_url']] != None:
            raise Exception("Singleton instance exists!")
        else:
            self.lock = threading.Lock()
            self.agent_base_url = kwargs['agent_base_url']
            BeatplayerRegistrar.__instances[self.agent_base_url] = self 
    
    def _get_device(self):
        # if not agent_base_url:
        #     if self.agent_base_url:
        #         logger.info("Client state requested with no agent base URL, using local value '%s'" % self.agent_base_url)
        #         agent_base_url = self.agent_base_url
        #     else:
        #         raise Exception("No value found in BeatplayerRegistrar.agent_base_url")
            # else:
            #     logger.info("Client state requested with no agent base URL, using settings value '%s'" % settings.BEATPLAYER_URL)
            #     agent_base_url = settings.BEATPLAYER_URL 
        device = Device.objects.filter(agent_base_url=self.agent_base_url).first()
        if not device:
            logger.info("No device was found with agent_base_url '%s'" % self.agent_base_url)
            device = Device(agent_base_url=self.agent_base_url)
        return device
        
    @contextmanager
    def device(self, read_only=False):
        if read_only:                        
            device = self._get_device()
            #logger.debug("Client state (r/o yield): %s" % device.status_dump())
            try:
                yield device
            finally:
                pass 
        else:        
            #logger.debug("Client state R/W request")    
            caller = traceback.format_stack()[-3].split(' ')[7].replace('\n', '')
            #logger.debug("%s wants to acquire client record lock.." % caller)
            self.lock.acquire()
            #logger.debug("%s has acquired client record lock" % caller)
            device = self._get_device()
            #logger.debug("Client state (yield): %s" % device.status_dump())
            try:
                yield device
            except:
                logger.error(sys.exc_info()[0])
                logger.error(sys.exc_info()[1])
                traceback.print_tb(sys.exc_info()[2])
            else:
                try:
                    if device.reachable and device.registered and device.selfreport and device.mounted:
                        device.status = Device.DEVICE_STATUS_READY
                    elif not device.reachable:
                        device.status = Device.DEVICE_STATUS_DOWN
                    else:
                        device.status = Device.DEVICE_STATUS_NOTREADY
                    if device.status != Device.DEVICE_STATUS_READY:
                        self.reassign_device()
                    self._show_beatplayer_status(device.status_dump())
                    #logger.debug("Client state (save): %s" % device.status_dump())
                    device.save()
                    self.lock.release()
                except Exception as e:
                    logger.error(sys.exc_info()[0])
                    logger.error(sys.exc_info()[1])
                    traceback.print_tb(sys.exc_info()[2])
    
    def log_health_response(self, health_data):
        with self.device() as device:
            now = get_localized_now()            
            device.mounted = health_data['music_folder_mounted']
            device.last_health_check = now

    def _show_beatplayer_status(self, beatplayer_status):
        _publish_event('beatplayer_status', beatplayer_status)
        
    def show_status(self):
        with self.device(read_only=True) as device:
            self._show_beatplayer_status(device.status_dump())
    
    def reassign_device(self):
        '''
        If this device is not ready, set its subscribers to another ready device  
        '''
        connection_ids_by_device = _get_switchboard_connection_id_for_device_id()
        with self.device(read_only=True) as device:
            if device.id in connection_ids_by_device:
                other_ready_devices = Device.objects.filter(Q(status=Device.DEVICE_STATUS_READY) & ~Q(id=device.id))
                if len(other_ready_devices) > 0:
                    logger.debug("The device we're looking at is NOT ready, %s clients care, and %s other device(s) are available" % (len(connection_ids_by_device[device.id]), len(other_ready_devices)))
                    for id in connection_ids_by_device[device.id]:
                        _publish_event(event='change_device', payload=json.dumps({'device_id': other_ready_devices[0].id}), connection_id=id)
                           
    def _call_agent(self, device):
        response = None 
        try:
            logger.info("Attempting registration: %s" % device.agent_base_url)
            beatplayer_client = client.ServerProxy(device.agent_base_url)
            response = beatplayer_client.register_client(settings.FRESHBEATS_CALLBACK_HEALTH_URL, device.agent_base_url)
            logger.info(" - %s registration response: %s" % (device.agent_base_url, response))
        except ConnectionRefusedError as cre:
            logger.error(sys.exc_info()[1])
        except:
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            #traceback.print_tb(sys.exc_info()[2])
            
        return response 
    
    def check_if_health_loop(self):
        with self.device(read_only=True) as device:
            if self.health_loop_thread:
                if self.health_loop_thread.is_alive():
                    logger.debug("%s -- Health loop is already alive" % device.agent_base_url)
                    return 
                else:
                    logger.debug("%s -- Health loop thread not alive, joining.." % device.agent_base_url)
                    self.health_loop_thread.join()
                    self.health_loop_thread = None 
            if device.is_active:                
                logger.warning(" - %s -- active, starting health loop" % device.agent_base_url)
                self.health_loop_thread = threading.Thread(target=self.run_health_loop)
                self.health_loop_thread.start()
            else:
                logger.info(" - %s -- inactive, not re-registering" % device.agent_base_url)
    
    def run_health_loop(self):
        '''
        Make MAX_REGISTRATION_ATTEMPTS attempts to register with self.device.
        If successful, start fresh checking in the same thread (abandon any loops here).
        If not successful or an exception raised for any other reason, call Device.register() and quit.
        '''
        try:                   
            logger.debug("Top of health loop..") 
            registration_attempts = 0
            no_report_count = 0
            iterations = 0
            since_last = None 
            sleep_time = 5
            dont_retry = False 
            while True:
                iterations += 1
                with self.device() as device:
                    if not device.registered:
                        registration_attempts += 1
                        response = self._call_agent(device)
                        device.reachable = response is not None 
                        device.registered = response is not None and response['data']['registered']
                        device.registered_at = get_localized_now() if device.registered else None 
                        dont_retry = response and 'data' in response and 'retry' in response['data'] and response['data']['retry'] == False                        
                    else:      
                        since_last = (get_localized_now() - device.last_health_check).total_seconds() if device.last_health_check else None 
                        no_report_count += 1 if not device.last_health_check else -no_report_count
                        device.selfreport = (since_last is not None and since_last < REGISTRATION_TIMEOUT)
                        device.registered = not (no_report_count > 2 or not device.selfreport)
                    
                    last_format = datetime.strftime(device.last_health_check, "%Y-%m-%d %H:%M:%S") if device.last_health_check else "-"
                    logger.debug("(%s) Registration - %s - attempts %s reachable? %s registered? %s last? %s/%s (%s)" % (iterations, device.agent_base_url, registration_attempts, device.reachable, device.registered, since_last, REGISTRATION_TIMEOUT, last_format))
                    
                    if iterations > HEALTH_LOOP_MAX_ITERATIONS:
                        logger.debug(" - %s -- health loop iteration MAX (%s/%s), breaking.." % (device.agent_base_url, iterations, HEALTH_LOOP_MAX_ITERATIONS))
                        break 
                        
                    if not device.registered:
                        if dont_retry or registration_attempts >= MAX_REGISTRATION_ATTEMPTS:
                            logger.info("  - %s --  not registered, quitting registration (dont_retry: %s)" % (device.agent_base_url, dont_retry))
                            break                        
                        else:
                            no_report_count = 0
                            device.selfreport = False 
                    else:
                        registration_attempts = 0
                                            
                    sleep_time = 5 if device.registered else registration_attempts*REGISTRATION_BACKOFF
                
                # -- do our sleeping outside the R/W context 
                logger.debug(" - %s - sleeping %s.." % (device.agent_base_url, sleep_time))
                time.sleep(sleep_time)
      
        except:
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
        finally:
            self.check_if_health_loop()
            
    
