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
# from django.contrib.sessions.backends.db import SessionStore 
# from django.contrib.sessions.models import Session 
from django.urls import reverse
from beater.switchboard.switchboard import SwitchboardClient
from beater.common.session import get_switchboard_connection_id_for_device_id
from beater.common.util import get_localized_now
from beater.models import Device, DeviceHealth
from beater.beatplayer.client import BeatplayerClient

REGISTRATION_TIMEOUT = int(os.getenv('FRESHBEATS_BEATPLAYER_REGISTRATION_TIMEOUT', 30))
REGISTRATION_BACKOFF = int(os.getenv('FRESHBEATS_BEATPLAYER_REGISTRATION_BACKOFF', 3))
REGISTRATION_HONEYMOON = int(os.getenv('FRESHBEATS_BEATPLAYER_REGISTRATION_HONEYMOON', 60))
MAX_REGISTRATION_ATTEMPTS = int(os.getenv('FRESHBEATS_BEATPLAYER_MAX_REGISTRATION_ATTEMPTS', 5))
HEALTH_LOOP_MAX_ITERATIONS = int(os.getenv('FRESHBEATS_BEATPLAYER_HEALTH_LOOP_MAX_ITERATIONS', 30))

def log_exception(logr):
    logr.error(f'{sys.exc_info()[0]}: {sys.exc_info()[1]}')
    traceback.print_tb(sys.exc_info()[2])

class BeatplayerHealth():
    
    __instances = {} 
    agent_base_url = None 
    device_lock = None 
    health_lock = None 
    health_loop_thread = None 
    
    logger = None
    health_reg_logger = None
    
    @staticmethod
    def getInstance(agent_base_url):
        # if not agent_base_url:
        #     logger.info("BeatplayerRegistrar instance requested with no agent base URL, using settings value '%s'" % settings.BEATPLAYER_URL)
        #     agent_base_url = settings.BEATPLAYER_URL
        if agent_base_url not in BeatplayerHealth.__instances or BeatplayerHealth.__instances[agent_base_url] == None:
            BeatplayerHealth(agent_base_url=agent_base_url)
        return BeatplayerHealth.__instances[agent_base_url] 
        
    def __init__(self, *args, **kwargs):
        if kwargs['agent_base_url'] in BeatplayerHealth.__instances and BeatplayerHealth.__instances[kwargs['agent_base_url']] != None:
            raise Exception("Singleton instance exists!")
        else:

            self.logger = logging.getLogger('beater.beatplayer.health')
            self.health_reg_logger = logging.getLogger('beater.beatplayer.health.reg')

            self.device_lock = threading.Lock()
            self.health_lock = threading.Lock()
            self.agent_base_url = kwargs['agent_base_url']
            # logger.exception()
            
            self.logger.debug(f'creating a BeatplayerHealth for {self.agent_base_url}')
            BeatplayerHealth.__instances[self.agent_base_url] = self 
    
    def _get_device(self):
        # if not agent_base_url:
        #     if self.agent_base_url:
        #         self.logger.info("Client state requested with no agent base URL, using local value '%s'" % self.agent_base_url)
        #         agent_base_url = self.agent_base_url
        #     else:
        #         raise Exception("No value found in BeatplayerRegistrar.agent_base_url")
            # else:
            #     self.logger.info("Client state requested with no agent base URL, using settings value '%s'" % settings.BEATPLAYER_URL)
            #     agent_base_url = settings.BEATPLAYER_URL 
        device = Device.objects.filter(agent_base_url=self.agent_base_url).first()        
        if not device:
            self.logger.info("No device was found with agent_base_url '%s'" % self.agent_base_url)
            device = Device(agent_base_url=self.agent_base_url)
        if not device.health:
            device.health = DeviceHealth.objects.create(status=DeviceHealth.DEVICE_STATUS_UNKNOWN)
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

        self.device_lock.acquire()
        self.health_lock.acquire()
        device = self._get_device()
        health = device.health 
        # health = DeviceHealth.objects.filter(device__agent_base_url=self.agent_base_url).first()
        # if not health:
        #     health = DeviceHealth.objects.create(status=DeviceHealth.DEVICE_STATUS_UNKNOWN)
        #     with self.device() as device:
        #         device.health = health
        yield health
        self._reconcile_status(health)
        health.save() 
        device.save()
        self.health_lock.release()
        self.device_lock.release()

    @contextmanager
    def device(self, read_only=False, logger=None):

        if not logger:
            logger = self.logger 

        if read_only:                        
            device = self._get_device()
            # logger.debug("Client state (r/o yield): %s" % device.status_dump())
            try:
                yield device
            finally:
                pass 
        else:        
            # logger.debug("Client state R/W request")    
            # caller = traceback.format_stack()[-3].split(' ')[7].replace('\n', '')
            # logger.debug("%s wants to acquire client record lock.." % caller)
            self.device_lock.acquire()
            self.health_lock.acquire()
            # logger.debug("%s has acquired client record lock" % caller)
            device = self._get_device()
            # logger.debug("Client state (yield): %s" % device.status_dump())
            try:
                yield device
            except:
                log_exception(logger)
            else:
                try:
                    logger.debug(f'device returned from yield, reconciling status and releasing locks')
                    self._reconcile_status(device.health)
                    
                    logger.debug("Client state (save): %s" % device.status_dump())
                    device.save()
                    device.health.save()
                    self.health_lock.release()
                    self.device_lock.release()
                    
                    if device.health.status != DeviceHealth.DEVICE_STATUS_READY:
                        self._reassign_device()
                    SwitchboardClient.getInstance().publish_event('beatplayer_status', device.status_dump())
                    
                except:
                    log_exception(logger)
                    # logger.error(sys.exc_info()[0])
                    # logger.error(sys.exc_info()[1])
                    # traceback.print_tb(sys.exc_info()[2])

    def update_beatplayer_status(self, player):
        with self.devicehealth() as health:
            player.beatplayer_status = health.status
            player.beatplayer_registered_at = health.registered_at
        player.save()

    def _healthz(self):
        '''Called by _reassign_device while monitoring one selected device to set current status on all the others.'''
    
        with self.device() as device:
            response = self._call_agent(device)
            if response:
                if 'data' in response and 'music_folder_mounted' in response['data']:
                    device.health.mounted = response['data']['music_folder_mounted']

    def log_client_presence(self):
        with self.devicehealth() as health:
            health.last_client_presence = get_localized_now()
            self.logger.debug("%s -- set last client presence: %s" % (self.agent_base_url, datetime.strftime(health.last_client_presence, "%c")))
        self.check_if_health_loop()

    def log_device_health_report(self, health_data):
        '''Incoming device health'''
        with self.devicehealth() as health:
            now = get_localized_now()            
            health.mounted = health_data['music_folder_mounted']
            health.last_device_health_report = now

    def _reassign_device(self):
        '''
        If this device is not ready, set its subscribers to another ready device  
        '''
        connection_ids_by_device = get_switchboard_connection_id_for_device_id()
        self.logger.debug(connection_ids_by_device)
        with self.device(read_only=True) as device:

            if device.id not in connection_ids_by_device:
                self.logger.debug("%s - this device has no websocket clients, nobody to switch" % device.agent_base_url)
                return 

            all_other_devices = Device.objects.filter(Q(is_active=True)  & ~Q(id=device.id))

            for d in [ f for f in all_other_devices if f.agent_base_url ]:
                beatplayer = BeatplayerHealth.getInstance(agent_base_url=d.agent_base_url)
                beatplayer._healthz()

            other_ready_devices = Device.objects.filter(Q(health__status=DeviceHealth.DEVICE_STATUS_READY) & ~Q(id=device.id))
            
            if len(other_ready_devices) == 0:
                self.logger.debug("%s - no other devices are ready, cannot switch" % device.agent_base_url)
                return 

            self.logger.debug("The device we're looking at is NOT ready, %s clients care, and %s other device(s) are available" % (len(connection_ids_by_device[device.id]), len(other_ready_devices)))
            
            for id in connection_ids_by_device[device.id]:
                self.logger.debug("%s - switching connection ID %s to device %s" % (device.agent_base_url, id, other_ready_devices[0].agent_base_url))
                SwitchboardClient.getInstance().publish_event(event='change_device', payload=json.dumps({'device_id': other_ready_devices[0].id}), connection_id=id)
                           
    def _call_agent(self, device, health_check_only=True):
        response = None 
        try:
            self.logger.info("Calling agent: %s (only health check? %s)" % (device.agent_base_url, health_check_only))
            # beatplayer_client = client.ServerProxy(device.agent_base_url)
            beatplayer_client = BeatplayerClient(device.agent_base_url)
            if health_check_only:
                response = beatplayer_client.healthz()                
            else:
                response = beatplayer_client.register_client(settings.FRESHBEATS_CALLBACK_HEALTH_URL, device.agent_base_url)
            self.logger.info(" - %s agent response: %s" % (device.agent_base_url, response))
        except ConnectionRefusedError as cre:
            self.logger.error(sys.exc_info()[1])
        except ConnectionError as ce:
            self.logger.error(sys.exc_info()[1])
        except:
            self.logger.error(sys.exc_info()[0])
            self.logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
        
        device.health.reachable = response is not None 
        
        return response 
    
    def check_if_health_loop(self, logger=None):

        if not logger:
            logger = self.logger 

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
                logger.debug(" - %s -- inactive, not re-registering" % device.agent_base_url)
                self._reassign_device()
                return 
            else:
                logger.debug(" - %s -- device is active, proceeding.." % device.agent_base_url)

            if not device.health.last_client_presence or not device.health.last_client_presence + timedelta(minutes=5) > get_localized_now():
                logger.debug(" - %s -- no clients present, not re-registering" % device.agent_base_url)
                return 
            else:
                logger.debug(" - %s -- device has a recent client presence, proceeding.." % device.agent_base_url)

            self.health_loop_thread = threading.Thread(target=self._run_health_loop)
            
            #TAG:MONITORING
            if settings.MONITORING_ENABLED:
                logger.warning(" - %s -- passed checks, starting health loop" % device.agent_base_url)
                self.health_loop_thread.start()
            else:
                logger.warning(f' - {device.agent_base_url} -- monitoring disabled, not starting health loop')
    
    def _run_health_loop(self):
        '''
        Make MAX_REGISTRATION_ATTEMPTS attempts to register with self.device.
        If successful, start fresh checking in the same thread (abandon any loops here).
        If not successful or an exception raised for any other reason, call Device.register() and quit.
        '''
        try:    

            self.health_reg_logger.debug("Entering health loop")                
            
            registration_attempts = 0
            iterations = 0
            seconds_since_last_device_health_report = None 
            sleep_time = 5
            dont_retry = False 

            while True:

                self.health_reg_logger.debug("/\/\/\/\/  Top of health loop  /\/\/\/\/") 

                iterations += 1

                with self.device() as device:

                    if device.health.registered_at:
                        
                        self.health_reg_logger.debug("(%s) Registered (%s), now verifying registration" % (device.agent_base_url, datetime.strftime(device.health.registered_at, "%Y-%m-%d %H:%M:%S")))
                        
                        honeymoon_is_over = (get_localized_now() - device.health.registered_at).total_seconds() < REGISTRATION_HONEYMOON
                        
                        if not device.health.last_device_health_report and not honeymoon_is_over:
                            self.health_reg_logger.debug("(%s) In registration honeymoon, we'll check back.." % device.agent_base_url)

                        elif device.health.last_device_health_report: # -- verify it's actually registered
                            seconds_since_last_device_health_report = (get_localized_now() - device.health.last_device_health_report).total_seconds()
                            if seconds_since_last_device_health_report >= REGISTRATION_TIMEOUT:
                                self.health_reg_logger.debug("(%s) We have a last check but it's %s seconds old, cancelling registration" % (device.agent_base_url, seconds_since_last_device_health_report))
                                device.health.registered_at = None 
                            else:
                                response = self._call_agent(device, health_check_only=True)
                                if not response:
                                    self.health_reg_logger.debug("(%s) No response from health-check-only call to agent, cancelling registration" % (device.agent_base_url))
                                    device.health.registered_at = None 
                                else:
                                    self.health_reg_logger.debug("(%s) Response from agent, registration is secure" % (device.agent_base_url))
                        elif honeymoon_is_over:
                            self.health_reg_logger.debug("(%s) Registered but no health report and honeymoon is over, cancelling registration" % device.agent_base_url)
                            device.health.registered_at = None 

                    else:
                        self.health_reg_logger.info("(%s) Device is NOT registered on health loop, attempting to register.." % device.agent_base_url)
                        registration_attempts += 1
                        response = self._call_agent(device, health_check_only=False)
                        if response:
                            if 'data' in response['response']['data'] and 'registered' in response['response']['data']['data'] and response['response']['data']['data']['registered']:
                                device.health.registered_at = get_localized_now() 
                                self.health_reg_logger.info(f'Successfully registered at {device.agent_base_url} at {device.health.registered_at}')
                            else:
                                self.health_reg_logger.warn(f'Failed to register at {device.agent_base_url}. {response["response"]["data"]}')

                            if 'data' in response and 'retry' in response['data'] and response['data']['retry'] == False:
                                self.health_reg_logger.warn(f'Will not retry registration at {device.agent_base_url}')
                                dont_retry = True 

                    last_format = '-'
                    registered_at_format = 'no'
                    if device.health.last_device_health_report:
                        last_format = datetime.strftime(device.health.last_device_health_report, "%Y-%m-%d %H:%M:%S")
                    if device.health.registered_at:
                        registered_at_format = "yes (%s)" % datetime.strftime(device.health.registered_at, "%Y-%m-%d %H:%M:%S")

                    self.health_reg_logger.debug("(%s) iter %s Registration - %s attempts, reachable? %s, registered? %s last? %s/%s (%s)" 
                        % (device.agent_base_url, iterations, registration_attempts, device.health.reachable, registered_at_format, seconds_since_last_device_health_report, REGISTRATION_TIMEOUT, last_format))
                    
                    if iterations > HEALTH_LOOP_MAX_ITERATIONS:
                        self.health_reg_logger.debug(" - %s -- health loop iteration MAX (%s/%s), breaking.." % (device.agent_base_url, iterations, HEALTH_LOOP_MAX_ITERATIONS))
                        break 
                        # _run_health_loop ?? why is this here? 
                    if not device.health.registered_at:
                        if dont_retry or registration_attempts >= MAX_REGISTRATION_ATTEMPTS:
                            self.health_reg_logger.info("  - %s --  not registered, quitting registration (dont_retry: %s)" % (device.agent_base_url, dont_retry))
                            break    
                        else:
                            sleep_time = registration_attempts * REGISTRATION_BACKOFF
                
                # -- do our sleeping outside the R/W context 
                self.health_reg_logger.debug(" - %s - sleeping %s.." % (device.agent_base_url, sleep_time))
                time.sleep(sleep_time)
      
        except:
            self.health_reg_logger.error(sys.exc_info()[0])
            self.health_reg_logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
        finally:
            self.check_if_health_loop(logger=self.health_reg_logger)
            
    
