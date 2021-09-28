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
from ..models import Device, DeviceHealth

REGISTRATION_TIMEOUT = int(os.getenv('FRESHBEATS_BEATPLAYER_REGISTRATION_TIMEOUT', 30))
REGISTRATION_BACKOFF = int(os.getenv('FRESHBEATS_BEATPLAYER_REGISTRATION_BACKOFF', 3))
REGISTRATION_HONEYMOON = int(os.getenv('FRESHBEATS_BEATPLAYER_REGISTRATION_HONEYMOON', 60))
MAX_REGISTRATION_ATTEMPTS = int(os.getenv('FRESHBEATS_BEATPLAYER_MAX_REGISTRATION_ATTEMPTS', 5))
HEALTH_LOOP_MAX_ITERATIONS = int(os.getenv('FRESHBEATS_BEATPLAYER_HEALTH_LOOP_MAX_ITERATIONS', 30))

logger = logging.getLogger(__name__)

class BeatplayerRegistrar():
    
    __instances = {} 
    agent_base_url = None 
    device_lock = None 
    health_lock = None 
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
            self.device_lock = threading.Lock()
            self.health_lock = threading.Lock()
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
    
    def _reconcile_status(self, device_health):
        if device_health.reachable and device_health.mounted:
            device_health.status = DeviceHealth.DEVICE_STATUS_READY
        elif not device_health.reachable:
            device_health.status = DeviceHealth.DEVICE_STATUS_DOWN
        else:
            device_health.status = DeviceHealth.DEVICE_STATUS_NOTREADY

    @contextmanager 
    def devicehealth(self):
        self.health_lock.acquire()
        health = DeviceHealth.objects.filter(device__agent_base_url=self.agent_base_url).first()
        yield health
        self._reconcile_status(health)
        health.save() 
        self.health_lock.release()

    @contextmanager
    def device(self, read_only=False):
        if read_only:                        
            device = self._get_device()
            # logger.debug("Client state (r/o yield): %s" % device.status_dump())
            try:
                yield device
            finally:
                pass 
        else:        
            # logger.debug("Client state R/W request")    
            caller = traceback.format_stack()[-3].split(' ')[7].replace('\n', '')
            logger.debug("%s wants to acquire client record lock.." % caller)
            self.device_lock.acquire()
            self.health_lock.acquire()
            logger.debug("%s has acquired client record lock" % caller)
            device = self._get_device()
            # logger.debug("Client state (yield): %s" % device.status_dump())
            try:
                yield device
            except:
                logger.error(sys.exc_info()[0])
                logger.error(sys.exc_info()[1])
                traceback.print_tb(sys.exc_info()[2])
            else:
                try:
                    self._reconcile_status(device.health)
                    
                    # logger.debug("Client state (save): %s" % device.status_dump())
                    device.save()
                    device.health.save()
                    self.health_lock.release()
                    self.device_lock.release()
                    
                    if device.health.status != DeviceHealth.DEVICE_STATUS_READY:
                        self.reassign_device()
                    _publish_event('beatplayer_status', device.status_dump())
                    
                except Exception as e:
                    logger.error(sys.exc_info()[0])
                    logger.error(sys.exc_info()[1])
                    traceback.print_tb(sys.exc_info()[2])
    
    def healthz(self):
        with self.device() as device:
            response = self._call_agent(device)
            if response:
                device.health.reachable = True 
                if 'data' in response and 'music_folder_mounted' in response['data']:
                    device.health.mounted = response['data']['music_folder_mounted']

    def log_client_presence(self):
        with self.devicehealth() as health:
            health.last_client_presence = get_localized_now()
            logger.debug("%s -- set last client presence: %s" % (self.agent_base_url, datetime.strftime(health.last_client_presence, "%c")))
        self.check_if_health_loop()

    def log_device_health_report(self, health_data):
        with self.devicehealth() as health:
            now = get_localized_now()            
            health.mounted = health_data['music_folder_mounted']
            health.last_device_health_report = now

    def reassign_device(self):
        '''
        If this device is not ready, set its subscribers to another ready device  
        '''
        connection_ids_by_device = _get_switchboard_connection_id_for_device_id()
        logger.debug(connection_ids_by_device)
        with self.device(read_only=True) as device:

            if device.id not in connection_ids_by_device:
                logger.debug("%s - this device has no websocket clients, nobody to switch" % device.agent_base_url)
                return 

            all_other_devices = Device.objects.filter(Q(is_active=True)  & ~Q(id=device.id))

            for d in all_other_devices:
                beatplayer = BeatplayerRegistrar.getInstance(agent_base_url=d.agent_base_url)
                beatplayer.healthz()

            other_ready_devices = Device.objects.filter(Q(health__status=DeviceHealth.DEVICE_STATUS_READY) & ~Q(id=device.id))
            
            if len(other_ready_devices) == 0:
                logger.debug("%s - no other devices are ready, cannot switch" % device.agent_base_url)
                return 

            logger.debug("The device we're looking at is NOT ready, %s clients care, and %s other device(s) are available" % (len(connection_ids_by_device[device.id]), len(other_ready_devices)))
            
            for id in connection_ids_by_device[device.id]:
                logger.debug("%s - switching connection ID %s to device %s" % (device.agent_base_url, id, other_ready_devices[0].agent_base_url))
                _publish_event(event='change_device', payload=json.dumps({'device_id': other_ready_devices[0].id}), connection_id=id)
                           
    def _call_agent(self, device, health_check_only=True):
        response = None 
        try:
            logger.info("Attempting registration: %s" % device.agent_base_url)
            beatplayer_client = client.ServerProxy(device.agent_base_url)
            if health_check_only:
                response = beatplayer_client.healthz()                
            else:
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
                    try:
                        self.health_loop_thread.join()
                    except RuntimeError as re:
                        pass 
                    self.health_loop_thread = None 
            else:
                logger.debug("%s -- No health loop thread" % device.agent_base_url)

            if not device.is_active:
                logger.info(" - %s -- inactive, not re-registering" % device.agent_base_url)
                self.reassign_device()
                return 
            else:
                logger.info(" - %s -- device is active, proceeding.." % device.agent_base_url)

            if not device.health.last_client_presence or not device.health.last_client_presence + timedelta(minutes=5) > get_localized_now():
                logger.info(" - %s -- no clients present, not re-registering" % device.agent_base_url)
                return 
            else:
                logger.info(" - %s -- device has a recent client presence, proceeding.." % device.agent_base_url)

            logger.warning(" - %s -- passed checks, starting health loop" % device.agent_base_url)
            self.health_loop_thread = threading.Thread(target=self.run_health_loop)
            self.health_loop_thread.start()
    
    def run_health_loop(self):
        '''
        Make MAX_REGISTRATION_ATTEMPTS attempts to register with self.device.
        If successful, start fresh checking in the same thread (abandon any loops here).
        If not successful or an exception raised for any other reason, call Device.register() and quit.
        '''
        try:                   
            logger.debug("Top of health loop..") 
            registration_attempts = 0
            iterations = 0
            seconds_since_last_device_health_report = None 
            sleep_time = 5
            dont_retry = False 

            while True:
                iterations += 1

                with self.device() as device:

                    if device.health.registered_at:
                        
                        logger.debug("(%s) Registered (%s), now verifying registration" % (device.agent_base_url, datetime.strftime(device.health.registered_at, "%Y-%m-%d %H:%M:%S")))

                        if not device.health.last_device_health_report and (get_localized_now() - device.health.registered_at).total_seconds() < REGISTRATION_HONEYMOON:
                            logger.debug("(%s) In registration honeymoon, we'll check back.." % device.agent_base_url)
                            pass # .. 

                        elif device.health.last_device_health_report: # -- verify it's actually registered
                            seconds_since_last_device_health_report = (get_localized_now() - device.health.last_device_health_report).total_seconds()
                            if seconds_since_last_device_health_report >= REGISTRATION_TIMEOUT:
                                logger.debug("(%s) We have a last check but it's not recent, cancelling registration" % device.agent_base_url)
                                device.health.registered_at = None 
                            else:
                                response = self._call_agent(device, health_check_only=True)
                                if not response:
                                    device.health.registered_at = None 
                        else:
                            logger.debug("(%s) Registered but no check and registration is old, cancelling registration" % device.agent_base_url)
                            device.health.registered_at = None 

                    else:
                        logger.info("(%s) Device is NOT registered on health loop, attempting to register.." % device.agent_base_url)
                        registration_attempts += 1
                        response = self._call_agent(device, health_check_only=False)
                        if response:
                            device.health.reachable = True 
                            if response['data']['registered']:
                                device.health.registered_at = get_localized_now() 

                            if 'data' in response and 'retry' in response['data'] and response['data']['retry'] == False:
                                dont_retry = True 

                    last_format = '-'
                    registered_at_format = 'no'
                    if device.health.last_device_health_report:
                        last_format = datetime.strftime(device.health.last_device_health_report, "%Y-%m-%d %H:%M:%S")
                    if device.health.registered_at:
                        registered_at_format = "yes (%s)" % datetime.strftime(device.health.registered_at, "%Y-%m-%d %H:%M:%S")

                    logger.debug("(%s) iter %s Registration - %s attempts, reachable? %s, registered? %s last? %s/%s (%s)" 
                        % (device.agent_base_url, iterations, registration_attempts, device.health.reachable, registered_at_format, seconds_since_last_device_health_report, REGISTRATION_TIMEOUT, last_format))
                    
                    if iterations > HEALTH_LOOP_MAX_ITERATIONS:
                        logger.debug(" - %s -- health loop iteration MAX (%s/%s), breaking.." % (device.agent_base_url, iterations, HEALTH_LOOP_MAX_ITERATIONS))
                        break 
                        
                    if not device.health.registered_at:
                        if dont_retry or registration_attempts >= MAX_REGISTRATION_ATTEMPTS:
                            logger.info("  - %s --  not registered, quitting registration (dont_retry: %s)" % (device.agent_base_url, dont_retry))
                            break    
                        else:
                            sleep_time = registration_attempts * REGISTRATION_BACKOFF
                
                # -- do our sleeping outside the R/W context 
                logger.debug(" - %s - sleeping %s.." % (device.agent_base_url, sleep_time))
                time.sleep(sleep_time)
      
        except:
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
        finally:
            self.check_if_health_loop()
            
    
