import os
import sys 
import json
import time
import subprocess
import traceback
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
logger_wrapper = logging.getLogger(__name__)
logger_wrapper.setLevel(level=logging._nameToLevel[WRAPPER_LOG_LEVEL.upper()])

class BaseWrapper():
    
    __metaclass__ = ABCMeta
    __instance = None 
    
    volume = None 
    music_folder = None     
    
    ps = None 
    
    muted = False # -- subclasses must manage this state 
    current_command = None 
    
    play_thread = None 
    
    @staticmethod 
    def getInstance(t=None):
        if BaseWrapper.__instance == None:
            if t:
                t()
            else:
                BaseWrapper()
        return BaseWrapper.__instance 
        
    def __init__(self, *args, **kwargs):
        if BaseWrapper.__instance != None:
            raise Exception("Already exists!")
        else:
            logger_wrapper.info("Creating BaseWrapper/%s singleton" % self.__class__.__name__)
            self.volume = int(BEATPLAYER_INITIAL_VOLUME)
            self.music_folder = os.getenv('BEATPLAYER_MUSIC_FOLDER', '/mnt/music')            
            logger_wrapper.info("  - music folder: %s" % self.music_folder)            
            logger_wrapper.info("  - volume: %s" % self.volume)
            for k in kwargs:
                val = kwargs[k]
                # -- handling comma-separated strings as lists 
                if type(kwargs[k]) == str and kwargs[k].count(",") > 0:
                    val = kwargs[k].split(',')
                logger_wrapper.debug("  - setting %s: %s" % (k, val))
                self.__setattr__(k, val)
            BaseWrapper.__instance = self 
    
    def _issue_command(self, command):
        logger_wrapper.debug("Issuing command: %s" % command)
        response = {'success': False, 'message': '', 'data': {}}
        try:
            if not self.ps or self.ps.poll() is not None:
                #self.ps = subprocess.Popen(command, stdin=subprocess.PIPE, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) #, stdout=self.f_outw, stderr=self.f_errw)
                self.ps = subprocess.Popen(command, stdin=subprocess.PIPE, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) #stdout=self.f_outw, stderr=self.f_errw)
                self.current_command = command 
                logger_wrapper.debug(' '.join(self.current_command) if self.current_command else None)
                response['success'] = True 
            else:
                response['message'] = "A process is running (%s), no action" % self.ps.pid
        except:
            response['message'] = str(sys.exc_info()[1])
            logger_wrapper.error(response['message'])
            logger_wrapper.error(sys.exc_info()[0])
            traceback.print_tb(sys.exc_info()[2])
        return response 
    
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
            logger_wrapper.error(response['message'])
            logger_wrapper.error(sys.exc_info()[0])
            traceback.print_tb(sys.exc_info()[2])
        return response 
        
    @classmethod
    def can_play(cls):
        result = False 
        try:
            ps = subprocess.Popen(["which", cls.executable_filename()], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = ps.wait() == 0
        except:
            logger_wrapper.error(sys.exc_info()[0])
            logger_wrapper.error(sys.exc_info()[1])                        
        return result
        
    def volume_down(self):
        if self.volume >= 5:
            self.volume -= 5
        else:
            self.volume = 0
        logger_wrapper.debug("new volume calculated: %s" % self.volume)
        return self.set_volume()
        
    def volume_up(self):
        if self.volume <= (100 - 5):
            self.volume += 5
        else:
            self.volume = 100
        logger_wrapper.debug("new volume calculated: %s" % self.volume)
        return self.set_volume()
        
    def validate_filepath(self, filepath):
        full_path = os.path.join(self.music_folder, filepath)
        if not os.path.exists(full_path):
            raise Exception("The file path %s does not exist" % full_path)    
    
    def is_muted(self):
        return self.muted
        
    def player_volume(self):
        return self.volume 
     
    def is_paused(self):
        return self.paused 
     
    @abstractmethod
    def play(self, filepath, callback_url=None):
        if callback_url:
            logger_wrapper.info("New thread to handle play: %s" % filepath)
            self.play_thread = ProcessMonitor.process(self.ps, callback_url, log_level=WRAPPER_LOG_LEVEL)
            # if not self.server:
            #     logger.player.info("Not running in server mode. Joining thread when done.")
            #     play_thread.join()
        
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
    
    def _play_command(self, filepath):
        command_line = "%s -ao alsa -slave -quiet" % self.player_path
        command = command_line.split(' ')
        command.append(os.path.join(self.music_folder, filepath))
        return command 
        
    def play(self, filepath):
        self.validate_filepath(filepath)
        return self._issue_command(self._play_command(filepath))
    
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
    paused = False # - mpv works on a toggle, as opposed to mplayer, which needs not track this state 
    socket_talker = None 
    mpv_socket = None 
    
    def executable_filename():
        return "mpv"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger_wrapper.info("Creating MPVWrapper")
        self.mpv_socket = os.getenv('MPV_SOCKET', '/tmp/mpv.sock')
        logger_wrapper.info("  - mpv socket: %s" % self.mpv_socket)
        self.socket_talker = MpvSocketTalker.getInstance(socket_file=self.mpv_socket, log_level=WRAPPER_LOG_LEVEL)
        
    def _play_command(self, filepath):
        command_line = "%s --quiet=yes --no-video --volume=%s --input-ipc-server=%s" % (self.player_path, self.volume, self.mpv_socket)
        command = command_line.split(' ')
        command.append(os.path.join(self.music_folder, filepath))
        logger_wrapper.debug(' '.join(command))
        return self._issue_command(command)
    
    def play(self, filepath, callback_url=None):
        self.validate_filepath(filepath)
        command_response = self._play_command(filepath)
        super().play(filepath, callback_url)
        return command_response 
            
    def stop(self):
        command = { 'command': [ "stop" ] }
        return self.socket_talker.send(command)
        
    def set_system_volume(self, volume):
        self._set_property("ao-volume", volume)
        
    def set_volume(self):
        self._set_property("volume", self.volume)

    def pause(self):
        self.paused = not self.paused 
        return self._set_property("pause", "yes" if self.paused else "no")
    
    def mute(self):        
        self.muted = not self.muted
        return self._set_property("mute", "yes" if self.muted else "no")
    
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
        socket_responses = self.socket_talker.send(command)
        logger_wrapper.debug("command: %s, response: %s" % (command, socket_responses))
        return self._normalize_socket_output(socket_responses)
            
    def _normalize_socket_output(self, socket_output):
        return socket_output[0] if len(socket_output) > 0 else None 
