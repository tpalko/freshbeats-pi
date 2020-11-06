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

WRAPPER_LOG_LEVEL = os.getenv('BEATPLAYER_WRAPPER_LOG_LEVEL', 'INFO')
logger_wrapper = logging.getLogger(__name__)
logger_wrapper.setLevel(level=logging._nameToLevel[WRAPPER_LOG_LEVEL.upper()])

class BaseWrapper():
    __metaclass__ = ABCMeta
    ps = None 
    volume = None 
    paused = False
    muted = False  
    current_command = None 
    
    def __init__(self, *args, **kwargs):
        self.volume = int(BEATPLAYER_INITIAL_VOLUME)
        for k in kwargs:
            val = kwargs[k]
            # -- handling comma-separated strings as lists 
            if type(kwargs[k]) == str and kwargs[k].count(",") > 0:
                val = kwargs[k].split(',')
            logger_wrapper.debug("setting %s: %s" % (k, val))
            self.__setattr__(k, val)
    
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
        response = {'success': False, 'message': '', 'data': {}}
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            attempts = 0
            while not os.path.exists("/tmp/mpv.sock"):
                if attempts > 15:
                    logger_wrapper.warning("tried 15 times over 30 seconds to find /tmp/mpv.sock, quitting")
                    break
                else:
                    logger_wrapper.warning("/tmp/mpv.sock does not exist.. waiting 2..")
                    attempts += 1
                    time.sleep(2)
            if os.path.exists("/tmp/mpv.sock"):
                logger_wrapper.debug("connecting to /tmp/mpv.sock for %s" % command)
                attempts = 0
                while not response['success'] and attempts < 10:
                    try:
                        attempts += 1
                        s.connect("/tmp/mpv.sock")
                        byte_count = s.send(bytes(json.dumps(command) + '\n', encoding='utf8'))
                        response['success'] = True 
                        response['data']['bytes_read'] = byte_count
                        logger_wrapper.debug("socket file read %s bytes on command %s" % (byte_count, command))
                    except:
                        logger_wrapper.warning("%s: will try again" % (str(sys.exc_info()[1])))
                        time.sleep(1)
                s.close()
            else:
                response['message'] = "/tmp/mpv.sock could not be found, command (%s) not sent" % command
        except:
            response['message'] = str(sys.exc_info()[1])
            logger_wrapper.error(response['message'])
            logger_wrapper.error(sys.exc_info()[0])
            traceback.print_tb(sys.exc_info()[2])
        return response 
        
    def can_play(self):
        result = False 
        try:
            ps = subprocess.Popen(["which", self.player_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = ps.wait() == 0
        except:
            logger_wrapper.error(str(sys.exc_info()[1]))
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
    
    def _play_command(self, filepath):
        command_line = "%s -ao alsa -slave -quiet" % self.player_path
        command = command_line.split(' ')
        command.append(filepath)
        return command 
        
    def play(self, filepath):
        return self._issue_command(self._play_command(filepath))
    
    def next(self, filepath):
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def play(self, filepath):
        command_line = "%s --quiet=yes --no-video --input-ipc-server=/tmp/mpv.sock" % self.player_path
        command = command_line.split(' ')
        command.append(filepath)
        logger_wrapper.debug(' '.join(command))
        return self._issue_command(command)
        
    def set_volume(self):
        logger_wrapper.debug("MPV set volume")
        command = { 'command': [ "set_property", "volume", self.volume ] }
        return self._send_to_socket(command)
        
    def stop(self):
        command = { 'command': [ "stop" ] }
        return self._send_to_socket(command)
    
    def pause(self):
        self.paused = not self.paused 
        command = { 'command': [ "set_property", "pause", "yes" if self.paused else "no" ] }
        return self._send_to_socket(command)
    
    def mute(self):
        self.muted = not self.muted
        command = { 'command': [ "set_property", "mute", "yes" if self.muted else "no" ] }
        return self._send_to_socket(command)
   
