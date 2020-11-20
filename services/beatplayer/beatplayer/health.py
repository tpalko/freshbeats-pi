#!/usr/bin/env python

import os
import sys
import signal
import traceback
import subprocess
import time
import shlex
from datetime import datetime 
import json
import logging
import requests
import threading
from wrappers import BaseWrapper 
from common.processmonitor import ProcessMonitor

HEALTH_LOG_LEVEL = os.getenv('BEATPLAYER_HEALTH_LOG_LEVEL', 'INFO')
logger_health = logging.getLogger(__name__)
logger_health.setLevel(level=logging._nameToLevel[HEALTH_LOG_LEVEL.upper()])

class PlayerHealth():

    sigint = False 
    api_clients = None 
    client_threads = None
    skip_mount_check = False 
    
    def __init__(self, *args, **kwargs):
        signal.signal(signal.SIGINT, self._sigint_handler())
        self.skip_mount_check = os.getenv('BEATPLAYER_SKIP_MOUNT_CHECK', '0') == '1'
        
        self.api_clients = {}
        self.client_threads = {}
            
    def _sigint_handler(self, player_handler=None):
        def handler(sig, frame):
            logger_health.warning("handling SIGINT")
            self.sigint = True             
            if player_handler:
                logger_health.warning("SIGINT handler running player handler..")
                player_handler()
            logger_health.warning("SIGINT handler joining %s client threads.." % len(self.client_threads))
            for callback_url in self.client_threads.keys():
                t = self.client_threads[callback_url]
                logger_health.warning(" - %s" % t.ident)
                if t.is_alive():
                    t.join(timeout=2)
                    if t.is_alive():
                        logger_health.warning("   - %s timed out" % t.ident)
                    else:
                        logger_health.warning("   - joined")
                else:
                    logger_health.warning("   - not alive")
            player = BaseWrapper.getInstance()
            if player.play_thread and player.play_thread.is_alive():     
                logger_health.warning("SIGINT handler joining play thread..")
                player.play_thread.join(timeout=10)
                if player.play_thread.is_alive():
                    logger_health.warning(" - %s timed out" % player.play_thread.ident)
                else:
                    logger_health.warning(" - %s joined" % player.play_thread.ident)
            logger_health.warning("Exiting!")
            sys.exit(0)
        return handler 
        
    def healthz(self):
        
        logger_health.debug("  Assessing player health..")
        
        player = BaseWrapper.getInstance()
        
        if not self.skip_mount_check:
            ps_df = subprocess.Popen(shlex.split("df"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            ps_grep = subprocess.Popen(shlex.split("grep %s" % player.music_folder), stdin=ps_df.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (out, err) = ps_grep.communicate(None)
            returncode = ps_grep.wait()
            music_folder_mounted = returncode == 0
            logger_health.debug("   - checked music folder %s mounted: %s" % (player.music_folder, music_folder_mounted))
        else:
            logger_health.debug("   - music folder mount check skipped")
            music_folder_mounted = True 
        
        response = {'success': False, 'message': '', 'data': {}}
        
        response['data'] = {
            'ps': {}, 
            'socket': {},
            'current_command': player.current_command, 
            'music_folder_mounted': music_folder_mounted
        }

        try:
            logger_health.debug("  - checking player stats:")
            # response['data']['paused'] = player.is_paused()
            # response['data']['volume'] = player.player_volume()
            # response['data']['muted'] = player.is_muted()
            response['data']['time'] = player.get_time()
            # response['data']['time_remaining'] = player.get_time_remaining()
            # response['data']['time_pos'] = player.get_time_pos()
            # response['data']['percent_pos'] = player.get_percent_pos()
            response['data']['socket']['healthy'] = True
        except ConnectionRefusedError as cre:
            logger_health.warning("Connection refused while checking some stats: %s" % sys.exc_info()[1])
            response['data']['socket']['healthy'] = False
            traceback.print_tb(sys.exc_info()[2])
        except OSError as oe:
            logger_health.warning("Fail while checking stats: %s" % sys.exc_info()[1])
            response['data']['socket']['healthy'] = False
            traceback.print_tb(sys.exc_info()[2])
        except:
            logger_health.error("Big Fail while checking some stats")
            response['data']['socket']['healthy'] = False
            logger_health.error(sys.exc_info()[0])
            logger_health.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
            
        try:
            returncode = -1
            pid = -1
            if player.ps:
                returncode = player.ps.poll()
                if returncode is None:
                    pid = player.ps.pid
            response['data']['ps']['returncode'] = returncode 
            response['data']['ps']['pid'] = pid
            response['data']['ps']['is_alive'] = ProcessMonitor.is_alive()
            response['success'] = True
        except:
            response['message'] = str(sys.exc_info()[1])
            logger_health.error(response['message'])
            traceback.print_tb(sys.exc_info()[2])
        return response
        
    def register_client(self, callback_url):
        response = {'success': False, 'message': '', 'data': {}}
        logger_health.debug("Registration request with callback %s" % callback_url)
        try:            
            def ping_client():
                client_ping_fails = 0
                while not self.sigint and callback_url in self.api_clients:  
                    logger_health.debug("*********************************")
                    logger_health.debug("*\t\t\t\t\t\t*")
                    logger_health.debug("* Running client health ping loop *")
                    logger_health.debug("*\t\t\t\t\t\t*")
                    logger_health.debug("*********************************")
                    player_health = None 
                    try:                  
                        player_health = self.healthz()
                        logger_health.debug(" - %s" % player_health)
                        try:
                            logger_health.debug(" - calling %s.." % callback_url)
                            callback_response = requests.post(callback_url, headers={'content-type': 'application/json'}, data=json.dumps(player_health))
                            if not callback_response or not callback_response.json()['success']:
                                raise Exception(" - no response or unsuccessful client ping to %s" % callback_url)
                            else:
                                logger_health.debug(" - success from %s" % callback_url)
                        except:
                            client_ping_fails += 1
                            logger_health.error("Client ping fail %s" % client_ping_fails)
                        if client_ping_fails > 5:
                            logger_health.warning("%s client_ping_fails to post callback URL %s, de-registering the client" % (5, callback_url))
                            del self.api_clients[callback_url]                   
                            del self.client_threads[callback_url]
                            break
                    except:
                        logger_health.error(str(sys.exc_info()[0]))
                        logger_health.error(str(sys.exc_info()[1]))
                        traceback.print_tb(sys.exc_info()[2])
                    if not player_health or 'ps' not in player_health['data'] or not player_health['data']['ps']['is_alive'] or not player_health['data']['socket']['healthy']:
                        if not self.sigint:
                            logger_health.debug(" - player doesn't seem to be up, sleeping..")
                            time.sleep(5)
                logger_health.warning("Exiting ping loop for %s (SIGINT: %s, api_clients: %s)" % (callback_url, self.sigint, callback_url in self.api_clients))
            register = True 
            if callback_url in self.api_clients and callback_url in self.client_threads:
                t = self.client_threads[callback_url]
                if t.is_alive():
                    register = False 
                    logger_health.info(" - client %s found with a living thread - not registering" % callback_url)
            if not register:
                message = "Client %s already registered (%s seconds ago)" % (callback_url, (datetime.now() - self.api_clients[callback_url]).total_seconds())
                response['message'] = message
                logger_health.info(message)
            else:
                if callback_url not in self.api_clients:
                    self.api_clients[callback_url] = datetime.now()
                if callback_url in self.client_threads:
                    t = self.client_threads[callback_url]
                    t.join(timeout=5)
                t = threading.Thread(target=ping_client)
                t.start()
                self.client_threads[callback_url] = t
                logger_health.info("Registered client %s" % callback_url)
                response['success'] = True 
            response['data']['registered'] = True 
            response['data']['retry'] = False
        except:
            response['message'] = str(sys.exc_info()[1])
            logger_health.error("Error attempting to register client:")
            logger_health.error(response['message'])
            traceback.print_tb(sys.exc_info()[2])
        return response 
