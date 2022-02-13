#!/usr/bin/env python3

import colorlog
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
from common.mpvsockettalker import PlayerNotRunningError

HEALTH_LOG_LEVEL = os.getenv('BEATPLAYER_HEALTH_LOG_LEVEL', 'INFO')

log_level = logging._nameToLevel[HEALTH_LOG_LEVEL.upper()]
color_formatter = colorlog.ColoredFormatter('%(log_color)s[ %(levelname)7s ] %(asctime)s %(filename)12s:%(lineno)-4d %(message)s')

logger_health = logging.getLogger(__name__)
logger_health.setLevel(level=log_level)
handler = colorlog.StreamHandler()
handler.setFormatter(color_formatter)
logger_health.addHandler(handler)

health_ping_loop_logger = logging.getLogger('health_ping_loop')
health_ping_loop_logger.setLevel(level=log_level)
f_handler = logging.FileHandler(filename='health_ping_loop.log', mode='a')
f_handler.setFormatter(color_formatter)
health_ping_loop_logger.addHandler(f_handler)

class PlayerHealth():

    sigint = False 
    api_clients = None 
    skip_mount_check = False 
    
    def __init__(self, *args, **kwargs):
        signal.signal(signal.SIGINT, self._sigint_handler(player_handler=kwargs['sigint_callback'] if 'sigint_callback' in kwargs else None))
        self.skip_mount_check = os.getenv('BEATPLAYER_SKIP_MOUNT_CHECK', '0') == '1'
        self.api_clients = {}
            
    def _sigint_handler(self, player_handler=None):
        def handler(sig, frame):
            logger_health.warning("handling SIGINT")
            self.sigint = True             
            if player_handler:
                logger_health.warning("SIGINT handler running player handler..")
                player_handler()
            logger_health.warning("SIGINT handler joining %s client threads.." % len(self.api_clients))
            for callback_url in self.api_clients.keys():
                t = self.api_clients[callback_url]['thread']
                logger_health.warning(" - %s" % t.ident)
                if t.is_alive():
                    t.join(timeout=2)
                    if t.is_alive():
                        logger_health.warning("   - %s timed out" % t.ident)
                    else:
                        logger_health.warning("   - joined")
                else:
                    logger_health.warning("   - not alive")
            logger_health.warning("Exiting!")
            sys.exit(0)
        return handler 
    
    def _get_health_response_template(self):
        return {
            'success': False, 
            'message': '', 
            'data': {
                'time': (0,0,),
                'ps': {
                    'returncode': None,
                    'pid': None,
                    'is_alive': False 
                },
                'socket': {
                    'healthy': True  # -- this is somewhat an arbitrary designation 
                },
                'current_command': None, 
                'music_folder_mounted': False
            }
        }

    def healthz(self):
        response = self._get_health_response_template()        
        player = BaseWrapper.getInstance(logger=logger_health)
        response['data']['music_folder_mounted'] = self._is_player_music_folder_mounted(player, logger_health)
        return response 

    def _is_player_music_folder_mounted(self, player, logger):
        music_folder_mounted = False 
        if not self.skip_mount_check:
            ps_df = subprocess.Popen(shlex.split("df"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            ps_grep = subprocess.Popen(shlex.split("grep %s" % player.music_folder), stdin=ps_df.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (out, err) = ps_grep.communicate(None)
            returncode = ps_grep.wait()
            music_folder_mounted = returncode == 0
            logger.debug("   - checked music folder %s mounted: %s" % (player.music_folder, music_folder_mounted))
        else:
            logger.debug("   - music folder mount check skipped")
            music_folder_mounted = True 
        
        return music_folder_mounted

    def get_health_report(self):
        
        health_ping_loop_logger.debug("  Assessing player health..")
        
        player = BaseWrapper.getInstance(logger=health_ping_loop_logger)
        
        response = self._get_health_response_template()
        response['data']['current_command'] = player.current_command
        response['data']['music_folder_mounted'] = self._is_player_music_folder_mounted(player, health_ping_loop_logger)
        
        try:
            health_ping_loop_logger.debug("  - checking player stats:")
            # -- these are local stats 
            response['data']['paused'] = player.is_paused()
            response['data']['volume'] = player.player_volume()
            response['data']['muted'] = player.is_muted()
            
            # -- this calls out to the socket 
            try:
                response['data']['time'] = player.get_time()
            except PlayerNotRunningError as pnre:
                health_ping_loop_logger.debug("Player not running while fetching time info")

            # response['data']['time_remaining'] = player.get_time_remaining()
            # response['data']['time_pos'] = player.get_time_pos()
            # response['data']['percent_pos'] = player.get_percent_pos()

        except RuntimeError as re:
            # [Errno 111] Connection refused during socket file /tmp/mpv.sock connect (_send)
            health_ping_loop_logger.error("Big Fail while checking some stats")
            health_ping_loop_logger.error(sys.exc_info()[0])
            traceback.print_tb(sys.exc_info()[2])
            response['data']['socket']['healthy'] = False 
        except Exception as e:
            health_ping_loop_logger.error(sys.exc_info()[0])
            health_ping_loop_logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
            response['data']['socket']['healthy'] = False 
            
        try:
            returncode = -1
            pid = -1
            if player.ps:
                returncode = player.ps.poll()
                if returncode is None:
                    pid = player.ps.pid
            response['data']['ps']['returncode'] = returncode 
            response['data']['ps']['pid'] = pid
            process_monitor = ProcessMonitor.getInstance()
            response['data']['ps']['is_alive'] = process_monitor.is_alive() or process_monitor.expired_less_than(seconds_ago=10)
            response['success'] = True
        except:
            response['message'] = str(sys.exc_info()[1])
            health_ping_loop_logger.error(response['message'])
            traceback.print_tb(sys.exc_info()[2])
        return response
        
    def register_client(self, callback_url, agent_base_url):
        response = {
            'success': False, 
            'message': '', 
            'data': {
                'registered': False,
                'retry': True
            }
        }
        
        logger_health.debug("Registration request with callback %s" % callback_url)
        try:            
            def ping_client():
                client_ping_fails = 0
                while not self.sigint and callback_url in self.api_clients:  
                    health_ping_loop_logger.debug("*********************************")
                    health_ping_loop_logger.debug("*\t\t\t\t\t\t*")
                    health_ping_loop_logger.debug("* Running client health ping loop *")
                    health_ping_loop_logger.debug("*\t\t\t\t\t\t*")
                    health_ping_loop_logger.debug("*********************************")
                    player_health = None 
                    try:                  
                        player_health = self.get_health_report()
                        player_health['data']['agent_base_url'] = agent_base_url
                        health_ping_loop_logger.debug(json.dumps(player_health, indent=4))
                        try:
                            health_ping_loop_logger.debug(" - calling %s.." % callback_url)
                            callback_response = requests.post(callback_url, headers={'content-type': 'application/json'}, data=json.dumps(player_health))
                            if not callback_response or not callback_response.json()['success']:
                                raise Exception(" - no response or unsuccessful client ping to %s" % callback_url)
                            else:
                                health_ping_loop_logger.debug(" - success from %s" % callback_url)
                        except:
                            client_ping_fails += 1
                            health_ping_loop_logger.error("Client ping fail %s" % client_ping_fails)
                        if client_ping_fails > 5:
                            health_ping_loop_logger.warning("%s client_ping_fails to post callback URL %s, de-registering the client" % (5, callback_url))
                            del self.api_clients[callback_url]                   
                            break
                    except:
                        health_ping_loop_logger.error(str(sys.exc_info()[0]))
                        health_ping_loop_logger.error(str(sys.exc_info()[1]))
                        traceback.print_tb(sys.exc_info()[2])
                        
                    if not player_health or 'ps' not in player_health['data'] or not player_health['data']['ps']['is_alive'] or not player_health['data']['socket']['healthy']:
                        if not self.sigint:
                            health_ping_loop_logger.debug(" - player doesn't seem to be up, sleeping..")
                            time.sleep(5)
                health_ping_loop_logger.warning("Exiting ping loop for %s (SIGINT: %s, in api_clients: %s)" % (callback_url, self.sigint, callback_url in self.api_clients))
            
            perform_registration = True 
            
            if callback_url in self.api_clients:
                t = self.api_clients[callback_url]['thread']
                if t.is_alive():
                    perform_registration = False 
                    logger_health.info(" - client %s found with a living thread - not registering" % callback_url)
                else:
                    logger_health.info(" - client %s not found or with a dead thread - registering" % callback_url)
                    
            if not perform_registration:
                message = "Client %s already registered (%s seconds ago)" % (callback_url, (datetime.now() - self.api_clients[callback_url]['registered_at']).total_seconds())
                response['message'] = message
                logger_health.info(message)
            else:
                if callback_url in self.api_clients:
                    logger_health.debug(f'Cleaning up existing {callback_url} registration..')
                    if self.api_clients[callback_url]['thread']:
                        logger_health.debug(f'   .. joining thread..')
                        t = self.api_clients[callback_url]['thread']
                        t.join(timeout=5)
                    logger_health.debug(f'   .. removing entry..')
                    del self.api_clients[callback_url]
                
                logger_health.info(f'Starting new thread for {callback_url} and creating registration..')
                
                t = threading.Thread(target=ping_client)
                self.api_clients[callback_url] = {'registered_at': datetime.now(), 'thread': t}
                t.start()
                
                logger_health.info("Registered client %s" % callback_url)
                response['success'] = True 
                
            response['message'] = f'Client {callback_url} is registered as of {self.api_clients[callback_url]["registered_at"]}'
            response['data']['registered'] = True 
            response['data']['retry'] = False
        except:
            response['message'] = str(sys.exc_info()[1])
            logger_health.error("Error attempting to register client:")
            logger_health.error(response['message'])
            traceback.print_tb(sys.exc_info()[2])
        
        logger_health.debug(json.dumps(response, indent=4))
        return response 
