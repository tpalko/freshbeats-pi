#!/usr/bin/env python3

import colorlog
import os
import sys 
import json
import time
import subprocess
import traceback
import threading
import socket
import logging 
try: #3
    from configparser import ConfigParser
except: #2
    from ConfigParser import ConfigParser

from abc import ABCMeta, abstractmethod
from common.processmonitor import ProcessMonitor
from common.mpvsockettalker import MpvSocketTalker

BEATPLAYER_DEFAULT_VOLUME = 90
BEATPLAYER_INITIAL_VOLUME = int(os.getenv('BEATPLAYER_INITIAL_VOLUME', BEATPLAYER_DEFAULT_VOLUME))

WRAPPER_LOG_LEVEL = os.getenv('BEATPLAYER_WRAPPER_LOG_LEVEL', 'INFO')
log_level = logging._nameToLevel[WRAPPER_LOG_LEVEL.upper()]
color_formatter = colorlog.ColoredFormatter('%(log_color)s[ %(levelname)7s ] %(asctime)s %(filename)12s:%(lineno)-4d %(message)s')

logger_wrapper = logging.getLogger(__name__)
logger_wrapper.setLevel(level=log_level)
handler = colorlog.StreamHandler()
handler.setFormatter(color_formatter)
logger_wrapper.addHandler(handler)

class BaseWrapper():
    
    __metaclass__ = ABCMeta
    __instance = None 
    
    volume = None 
    music_folder = None     
    
    ps = None 
    
    muted = False # -- subclasses must manage this state 
    paused = False # - mpv works on a toggle, as opposed to mplayer, which needs not track this state 
    current_command = None 
    logger = None 
    
    @staticmethod 
    def getInstance(t=None, logger=None):
        if BaseWrapper.__instance == None:
            if t:
                t()
            else:
                BaseWrapper()
        i = BaseWrapper.__instance 
        if logger:
            i.logger = logger 
        return i
        
    def __init__(self, *args, **kwargs):
        if BaseWrapper.__instance != None:
            raise Exception("Already exists!")
        else:
            self.logger = logger_wrapper 
            
            self.logger.info("Creating BaseWrapper/%s singleton" % self.__class__.__name__)
            self.volume = int(BEATPLAYER_INITIAL_VOLUME)
            self.music_folder = os.getenv('BEATPLAYER_MUSIC_FOLDER', '/mnt/music')            
            self.logger.info("  - music folder: %s" % self.music_folder)            
            self.logger.info("  - volume: %s" % self.volume)
            for k in kwargs:
                val = kwargs[k]
                # -- handling comma-separated strings as lists 
                if type(kwargs[k]) == str and kwargs[k].count(",") > 0:
                    val = kwargs[k].split(',')
                self.logger.debug("  - setting %s: %s" % (k, val))
                self.__setattr__(k, val)
            BaseWrapper.__instance = self 
    
    def _issue_command(self, url, filepath, callback_url, agent_base_url):
        response = {'success': False, 'message': '', 'data': {}}
        filepath_validation_message = self._validate_filepath(filepath)
        if filepath_validation_message:
            self.logger.warning(filepath_validation_message)
            response['message'] = filepath_validation_message
        else:
            command = self._command_generator(url, filepath)
            self.logger.debug("Issuing command: %s" % command)
            try:
                while self.is_playing():
                    self.stop()
                    time.sleep(1)
                #self.ps = subprocess.Popen(command, stdin=subprocess.PIPE, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) #, stdout=self.f_outw, stderr=self.f_errw)
                self.ps = subprocess.Popen(command, stdin=subprocess.PIPE, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) #stdout=self.f_outw, stderr=self.f_errw)
                
                process_monitor = ProcessMonitor.getInstance()
                process_monitor.process(self.ps, callback_url, agent_base_url, log_level=WRAPPER_LOG_LEVEL)
                
                self.current_command = command 
                self.logger.debug(' '.join(self.current_command) if self.current_command else None)
                response['success'] = True 
            except:
                response['message'] = str(sys.exc_info()[1])
                self.logger.error(response['message'])
                self.logger.error(sys.exc_info()[0])
                traceback.print_tb(sys.exc_info()[2])
        return response 
    
    def _validate_filepath(self, filepath):
        if not os.path.exists(os.path.join(self.music_folder, filepath)):
            return "The filepath %s does not exist" % filepath 
        return None
        
    def _send_to_process(self, command):
        response = {'success': False, 'message': '', 'data': {}}
        try:
            if self.ps and self.ps.poll() is None:
                self.ps.stdin.write("%s\n" % (command))
                response['success'] = True
            else:
                response['message'] = "No process is running"
        except:
            response['message'] = str(sys.exc_info()[1])
            self.logger.error(response['message'])
            self.logger.error(sys.exc_info()[0])
            traceback.print_tb(sys.exc_info()[2])
        return response 
    
    @abstractmethod 
    def _command_generator(self, url, filepath):
        pass 
                
    @classmethod
    def can_play(cls):
        result = False 
        try:
            ps = subprocess.Popen(["which", cls.executable_filename()], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = ps.wait() == 0
        except:
            self.logger.error(sys.exc_info()[0])
            self.logger.error(sys.exc_info()[1])                        
        return result
        
    def is_playing(self):
        return self.ps is not None and self.ps.poll() is None 
     
    def is_muted(self):
        return self.muted

    def player_volume(self):
        return self.volume 

    def is_paused(self):
        return self.paused 
            
    # -- exposed controls 
    
    def volume_down(self):
        if self.volume >= 5:
            self.volume -= 5
        else:
            self.volume = 0
        self.logger.debug("new volume calculated: %s" % self.volume)
        return self.set_volume()
        
    def volume_up(self):
        if self.volume <= (100 - 5):
            self.volume += 5
        else:
            self.volume = 100
        self.logger.debug("new volume calculated: %s" % self.volume)
        return self.set_volume()
        
    @abstractmethod
    def play(self, url, filepath, callback_url, agent_base_url):
        pass         
        
    @abstractmethod
    def stop(self):
        pass
        
    @abstractmethod
    def pause(self):
        pass 
    
    @abstractmethod
    def mute(self):
        pass 
        
class MPlayerWrapper(BaseWrapper):
    
    player_path = "mplayer"
    
    def executable_filename():
        return "mplayer"
    
    def _command_generator(self, url, filepath):
        command_line = "%s -ao alsa -slave -quiet" % self.player_path
        command = command_line.split(' ')
        command.append(os.path.join(self.music_folder, filepath))
        return command 
        
    # exposed controls 
    
    def play(self, url, filepath, callback_url, agent_base_url):
        return self._issue_command(url, filepath, callback_url, agent_base_url)
    
    def stop(self):
        return self._send_to_process("stop")
        
    def pause(self):
        self.paused = not self.paused 
        return self._send_to_process("pause")

    def mute(self):
        self.muted = not self.muted
        return self._send_to_process("mute %s" % ("1" if self.muted else "0"))
    
    def set_volume(self):
        return self._send_to_process("volume %s 1" % self.volume)
        
class MPVWrapper(BaseWrapper):
    
    '''
    command set_property
        - audio-files ...
        - playlist-start 1
        - playlist-pos 0-n-1
    '''
    
    player_path = "mpv"    
    socket_talker = None 
    mpv_socket = None 
    
    def executable_filename():
        return "mpv"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.info("Creating MPVWrapper")
        self.mpv_socket = os.getenv('MPV_SOCKET', '/tmp/mpv.sock')
        self.logger.info("  - mpv socket: %s" % self.mpv_socket)
        self.socket_talker = MpvSocketTalker.getInstance(socket_file=self.mpv_socket, log_level=WRAPPER_LOG_LEVEL)
        
    def _command_generator(self, url, filepath):
        command_line = "%s --quiet=yes --no-video --volume=%s --input-ipc-server=%s" % (self.player_path, self.volume, self.mpv_socket)
        # mpv https://www.youtube.com/watch?v=e4TFD2PfVPw
        command = command_line.split(' ')
        if url is not None:
            command.append(url)
        else:
            command.append(os.path.join(self.music_folder, filepath))
        self.logger.debug(' '.join(command))
        return command
    
    def get_time_remaining(self):
        return self._get_property("time-remaining")
    
    def get_time_pos(self):
        return self._get_property("time-pos")
        
    def get_time(self):
        time_pos = self.get_time_pos()
        time_remaining = self.get_time_remaining()
        return (time_pos, time_remaining)
    
    def get_percent_pos(self):
        return self._get_property("percent-pos")
    
    def _set_property(self, property, value):
        return self._send_to_socket({ 'command': [ "set_property", property, value ] })
        
    def _get_property(self, property):
        return self._send_to_socket({ 'command': [ "get_property", property ] })
        
    def _send_to_socket(self, command):
        multi_response = False 
        socket_responses = self.socket_talker.send(command, multi_response=multi_response)
        self.logger.debug("command: %s, response: %s" % (command, socket_responses))
        if multi_response:
            return socket_responses[0] if len(socket_responses) > 0 else None
        else:
            return socket_responses
            
    # exposed controls 
    
    def play(self, url, filepath, callback_url, agent_base_url):
        
        command_thread = threading.Thread(target=self._issue_command, args=(url, filepath, callback_url, agent_base_url,))
        command_thread.start()
        
        return {'success': True, 'message': '', 'data': {}}
    
    def stop(self):
        process_monitor = ProcessMonitor.getInstance()
        process_monitor.report_complete = False 
        command = { 'command': [ "stop" ] }
        return { "success": True, "data": self.socket_talker.send(command) }
        
    def set_system_volume(self, volume):
        return { "success": True, "data": self._set_property("ao-volume", volume) }
        
    def set_volume(self):
        return { "success": True, "data": self._set_property("volume", self.volume) }

    def pause(self):
        self.paused = not self.paused 
        return { "success": True, "data": self._set_property("pause", "yes" if self.paused else "no") }
    
    def mute(self):        
        self.muted = not self.muted
        return { "success": True, "data": self._set_property("mute", "yes" if self.muted else "no") }
    
