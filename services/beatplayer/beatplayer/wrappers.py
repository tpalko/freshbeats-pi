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
    mpv_socket = None 
    
    ps = None 
    
    muted = False  
    current_command = None 
    
    @staticmethod 
    def getInstance(t=None):
        if t and BaseWrapper.__instance == None:
            t()
        return BaseWrapper.__instance 
        
    def __init__(self, *args, **kwargs):
        if BaseWrapper.__instance != None:
            raise Exception("Already exists!")
        else:
            self.volume = int(BEATPLAYER_INITIAL_VOLUME)
            self.music_folder = os.getenv('BEATPLAYER_MUSIC_FOLDER', '/mnt/music')
            self.mpv_socket = os.getenv('MPV_SOCKET', '/tmp/mpv.sock')
            logger_wrapper.info("music folder: %s" % self.music_folder)
            for k in kwargs:
                val = kwargs[k]
                # -- handling comma-separated strings as lists 
                if type(kwargs[k]) == str and kwargs[k].count(",") > 0:
                    val = kwargs[k].split(',')
                logger_wrapper.debug("setting %s: %s" % (k, val))
                self.__setattr__(k, val)
            BaseWrapper.__instance = self 
    
    def _issue_command(self, command):
        response = {'success': False, 'message': '', 'data': {}}
        try:
            if not self.ps or self.ps.poll() is not None:
                #self.ps = subprocess.Popen(command, stdin=subprocess.PIPE, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) #, stdout=self.f_outw, stderr=self.f_errw)
                self.ps = subprocess.Popen(command, stdin=subprocess.PIPE, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) #stdout=self.f_outw, stderr=self.f_errw)
                self.current_command = command 
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
    
    def _send_to_socket(self, command):
        logger_wrapper.debug("_send_to_socket: %s" % command)
        response = {'success': False, 'message': '', 'data': ""}
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            attempts = 0
            while not os.path.exists(self.mpv_socket):
                if attempts > 15:
                    logger_wrapper.warning("tried 15 times over 30 seconds to find %s, quitting" % self.mpv_socket)
                    break
                else:
                    logger_wrapper.warning("%s does not exist.. waiting 2.." % self.mpv_socket)
                    attempts += 1
                    time.sleep(2)
            if os.path.exists(self.mpv_socket):
                logger_wrapper.debug("connecting to %s for %s" % (self.mpv_socket, command))
                attempts = 0
                while not response['success'] and attempts < 1:
                    try:
                        attempts += 1
                        s.connect(self.mpv_socket)
                        s.settimeout(2)
                        byte_count = s.send(bytes(json.dumps(command) + '\n', encoding='utf8'))
                        response['success'] = True 
                        #response['data']['bytes_read'] = byte_count                        
                        while True:
                            try:
                                response['data'] = "%s%s" % (response['data'], s.recv(1024))
                            except socket.timeout as t:
                                break 
                        logger_wrapper.debug("socket file read %s bytes on command %s" % (len(response['data']), command))
                    except:
                        logger_wrapper.warning("%s: will try again" % (str(sys.exc_info()[1])))
                        time.sleep(1)
                s.close()
            else:
                response['message'] = "%s could not be found, command (%s) not sent" % (self.mpv_socket, command)
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
            
    @abstractmethod
    def play(self, filepath):
        pass 
        
    @abstractmethod
    def next(self, filepath):
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
    
    def _play_command(self, filepath):
        command_line = "%s -ao alsa -slave -quiet" % self.player_path
        command = command_line.split(' ')
        command.append(os.path.join(self.music_folder, filepath))
        return command 
        
    def play(self, filepath):
        self.validate_filepath(filepath)
        return self._issue_command(self._play_command(filepath))
    
    def next(self, filepath):
        self.validate_filepath(filepath)
        stop_response = self._send_to_process("stop")
        return self._issue_command(self._play_command(filepath))

    def stop(self):
        return self._send_to_process("stop")
        
    def pause(self):
        return self._send_to_process("pause")

    def mute(self):
        self.muted = False if self.muted else True
        return self._send_to_process("mute %s" % ("1" if self.muted else "0"))
    
    def set_volume(self):
        return self._send_to_process("volume %s 1" % self.volume)
    
    # def next(self):
    # 
    #     response = {'success': False, 'message': ''}
    #     try:
    #         self._issue_command("pt_step 1")
    #         response['success'] = True 
    #     except:
    #         response['message'] = sys.exc_info()[1]
    # 
    #     return response 
        
class MPVWrapper(BaseWrapper):
    
    '''
    command set_property
        - audio-files ...
        - playlist-start 1
        - playlist-pos 0-n-1
    '''
    
    player_path = "mpv"
    paused = False
    
    def executable_filename():
        return "mpv"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def _play_command(self, filepath):
        command_line = "%s --quiet=yes --no-video --volume=%s --input-ipc-server=%s" % (self.player_path, self.volume, self.mpv_socket)
        command = command_line.split(' ')
        command.append(os.path.join(self.music_folder, filepath))
        logger_wrapper.debug(' '.join(command))
        return self._issue_command(command)
    
    def play(self, filepath):
        self.validate_filepath(filepath)
        return self._play_command(filepath)
            
    def next(self, filepath):
        self.validate_filepath(filepath)
        stop_response = self.stop()
        return self._play_command(filepath)

    def stop(self):
        command = { 'command': [ "stop" ] }
        return self._send_to_socket(command)
        
    def set_system_volume(self, volume):
        self._set_property("ao-volume", volume)
        
    def set_player_volume(self):
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
        return self._get_property("time_pos")
    
    def get_percent_pos(self):
        return self._get_property("percent-pos")
        
    def is_paused(self):
        return self._get_property("pause")
    
    def is_muted(self):
        return self._get_property("mute")
        
    def player_volume(self):
        return self._get_property("volume")
    
    def _set_property(self, property, value):
        logger_wrapper.info("Set property: %s <- %s" % (property, value))
        command = { 'command': [ "set_property", property, value ] }
        return self._send_to_socket(command)
   
    def _get_property(self, property):
        command = { 'command': [ "get_property", property ] }
        socket_response = self._send_to_socket(command)
        logger_wrapper.debug(socket_response)
        socket_data = json.loads(socket_response['data'])
        return socket_data['data']
    
    def properties_available(self):
        command = { 'command': [ "get_property", "volume" ] }
        socket_response = self._send_to_socket(command)
        logger_wrapper.debug(socket_response)
        if socket_response['success'] and socket_response['data'] != '':
            socket_data = json.loads(socket_response['data'].decode())
            return socket_data['error'] == "success"
        return False 
    
   
