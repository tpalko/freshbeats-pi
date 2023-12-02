import os 
import threading 
import sys 
import subprocess

from ..basewrapper import BaseWrapper 
from beatplayer.common.mpvsockettalker import MpvSocketTalker
from beatplayer.common.processmonitor import ProcessMonitor
from beatplayer.common.mpvsockettalker import PlayerNotRunningError

MPV_SOCKET_DEFAULT = '/tmp/mpv.sock'

class main(BaseWrapper):
    
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
        return main.player_path 
    
    def __init__(self, *args, **kwargs):
        
        self.mpv_socket = os.getenv('MPV_SOCKET', MPV_SOCKET_DEFAULT)
        
        super().__init__(*args, **kwargs)

        self.logger.info("  - mpv socket: %s" % self.mpv_socket)

        self.logger.info("Creating MPVWrapper")
        
        self.socket_talker = MpvSocketTalker.getInstance(socket_file=self.mpv_socket)
    
    def _init(self):
        ps = subprocess.Popen(f'{self.player_path} --input-ipc-server={self.mpv_socket}'.split(' '), stdin=subprocess.PIPE, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = ps.communicate(None)

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
        socket_response = None 
        success = False 

        try:
            socket_response = self.socket_talker.send(command)
            success = True
        except PlayerNotRunningError as pnre:            
            self.logger.info(f'Player not running, cannot stop')

        return { "success": success, "data": socket_response }
        
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

        
