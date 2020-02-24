#!/usr/bin/env python

import os
import socket
import sys
import traceback
import subprocess
import time
from datetime import datetime 
import json
try: #3
    from xmlrpc.server import SimpleXMLRPCServer
except: #2
    from SimpleXMLRPCServer import SimpleXMLRPCServer
import logging
from optparse import OptionParser
import requests
try: #3
    from configparser import ConfigParser
except: #2
    from ConfigParser import ConfigParser
import threading
from abc import ABCMeta, abstractmethod

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

urllib_logger = logging.getLogger('requests.packages.urllib3.connectionpool')
urllib_logger.setLevel(level=logging.WARN)

class BaseClient():
    __metaclass__ = ABCMeta
    ps = None 
    volume = None 
    current_command = None 
    
    def __init__(self, *args, **kwargs):
        self.volume = os.getenv('BEATPLAYER_DEFAULT_VOLUME')
        for k in kwargs:
            val = kwargs[k]
            # -- handling comma-separated strings as lists 
            if type(kwargs[k]) == str and kwargs[k].count(",") > 0:
                val = kwargs[k].split(',')
            self.__setattr__(k, val)
        self.logger = logging.getLogger(__name__)
    
    def _issue_command(self, command):
        response = {'success': False, 'message': '', 'data': {}}
        try:
            if self.ps and self.ps.poll() is None:
                self.ps.stdin.write("%s\n" % (command))
            else:
                #self.ps = subprocess.Popen(command, stdin=subprocess.PIPE, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) #, stdout=self.f_outw, stderr=self.f_errw)
                self.ps = subprocess.Popen(command, stdin=subprocess.PIPE, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) #stdout=self.f_outw, stderr=self.f_errw)
                self.current_command = command 
            response['success'] = True
        except:
            response['message'] = str(sys.exc_info()[1])
            logger.error(response['message'])
            logger.error(sys.exc_info()[0])
            traceback.print_tb(sys.exc_info()[2])
        return response 
        
    def healthz(self):
        data = {'data': {'ps': {}, 'volume': self.volume, 'current_command': self.current_command}}
        try:
            returncode = -1
            pid = -1
            if self.ps:
                returncode = self.ps.poll()
                if returncode is None:
                    pid = self.ps.pid
            data['data']['ps']['returncode'] = returncode 
            data['data'['ps']['pid'] = pid
        except:
            logger.error(response['message'])
            traceback.print_tb(sys.exc_info()[2])
        return data
        
    def can_play(self):
        ps = subprocess.Popen([self.player_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return ps.wait() == 0
        
    @abstractmethod
    def play(self, filepath):
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
    
    @abstractmethod
    def volume_up(self):
        pass
    
    @abstractmethod
    def volume_down(self):
        pass

class MPlayerClient(BaseClient):
    
    player_path = "mplayer"
    
    def play(self, filepath):
        command_line = "%s -ao alsa -slave -quiet" % self.player_path
        command = command_line.split(' ')
        command.append(filepath)
        self._issue_command(command)
        
    
    def pause(self):
        return self._issue_command("pause")

    def stop(self):
        return self._issue_command("stop")

    def mute(self):
        self.is_muted = False if self.is_muted else True
        return self._issue_command("mute %s" % ("1" if self.is_muted else "0"))
    
    def set_volume(self):
        self._issue_command("volume %s 1" % self.volume)
        
    def volume_down(self):
        if self.volume >= 5:
            self.volume -= 5
        else:
            self.volume = 0
        response = self._issue_command("volume %s 1" % self.volume)
        response['data']['volume'] = self.volume
        return response
    
    def volume_up(self):
        if self.volume <= (100 - 5):
            self.volume += 5
        else:
            self.volume = 100
        response = self._issue_command("volume %s 1" % self.volume)
        response['data']['volume'] = self.volume
        return response
    
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
        
class MPVClient(BaseClient):
    
    '''
    command set_property
        - audio-files ...
        - playlist-start 1
        - playlist-pos 0-n-1
    '''
    
    player_path = "mpv"
    paused = False 
    s = None 
    volume = None 
    
    def __init__(self, *args, **kwargs):
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.s.connect('/tmp/mpv.sock')
        super().__init__(*args, **kwargs)
        
    def play(self, filepath):
        command_line = "%s --quiet --input-unix-socket=/tmp/mpv.sock" % self.player_path
        command = command_line.split(' ')
        command.append(filepath)
        logger.debug(' '.join(command))
        self.current_command = command 
        self.ps = subprocess.Popen(command, stdin=subprocess.PIPE, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("mplayer command called..")
    
    def set_volume(self):
        command = { 'command': [ "set_property", "volume", self.volume ] }
        response = self.s.sendall(command)
        logger.info(response)
        
    def stop(self):
        command = { 'command': [ "stop" ] }
        response = self.s.sendall(command)
        logger.info(response)
    
    def pause(self):
        command = { 'command': [ "set_property", pause, not self.paused ] }
        response = self.s.sendall(command)
        logger.info(response)
        if response['error'] == 'success':
            self.paused = not self.paused 
        else:
            logger.error("pause failed")

class MPPlayer():
    
    current_thread = None
    api_clients = {}
    player_clients = [MPVClient, MPlayerClient]
    player = None 

    def __init__(self, *args, **kwargs):

        self.f_outw = open("mplayer.out", "wb")
        self.f_errw = open("mplayer.err", "wb")

        self.f_outr = open("mplayer.out", "rb")
        self.f_errr = open("mplayer.err", "rb")

        self.music_folder = '/mnt/music'
        
        for p in self.player_clients:
            i = p()
            if i.can_play():
                self.player = i
                break             
        
        if not self.player:
            raise Excption("No suitable player exists")   
        
        self.default_volume = os.getenv('BEATPLAYER_DEFAULT_VOLUME')
        self.player_path = os.getenv('PLAYER_PATH')        
        
        logger.info("music folder: %s" % self.music_folder)
        logger.info("default volume: %s" % self.default_volume)

        self.is_muted = False
    
    def register_client(self, callback_url):
        response = {'success': False, 'message': '', 'data': {}}
        try:            
            def ping_client():
                while True:  
                    try:                  
                        player_health = self.healthz()
                        logger.debug(player_health)
                        callback_response = requests.post(callback_url, headers={'content-type': 'application/json'}, data=json.dumps(player_health))
                        if not callback_response or not callback_response.json()['success']:
                            raise 
                    except:
                        logger.warn("Failed to post callback URL %s, de-registering the client" % callback_url)
                        del self.api_clients[callback_url]
                        break
                    time.sleep(5)
                logger.warn("Exiting ping loop for %s" % callback_url)
            if callback_url not in self.api_clients:
                self.api_clients[callback_url] = datetime.now()
                t = threading.Thread(target=ping_client)
                t.start()
                logger.info("Registered client %s" % callback_url)
                response['success'] = True 
            else:
                response['message'] = "Client %s already registered (%s)" % (callback_url, (datetime.now() - self.api_clients[callback_url]).total_seconds())
        except:
            response['message'] = str(sys.exc_info()[1])
            logger.error("Error attempting to register client:")
            logger.error(response['message'])
        return response 

    def get_music_folder(self):
        return self.music_folder

    def logs(self):
        self.f_outr.seek(0)
        lines = list(self.f_outr)
        return lines

    # def get_player_info(self):
    # 
    #     try:
    # 
    #         self.f_outr.seek(0)
    #         lines = list(self.f_outr)
    # 
    #         info = {}
    #         labels = ["Playing ", " Title: ", " Artist: ", " Album: ", " Year: ", " Comment: ", " Track: ", " Genre: "]
    # 
    #         for l in lines:
    #             for b in labels:
    #                 if l.find(b) == 0:
    #                     info[b.strip().replace(':', '')] = l[len(b):len(l)].strip().replace('\n', '')
    # 
    #         return info
    #     except Exception as e:
    #         logger.error(sys.exc_info())
    #         traceback.print_tb(sys.exc_info()[2])

    def play(self, filepath, callback_url, force=False):#, match=None):
        
        response = {'success': False, 'message': '', 'data': {}}
        logger.debug("Playing %s (%sforcing)" %(filepath, "" if force else "not "))
            
        try:

            if not os.path.exists(filepath):
                #call_callback(1, msg)
                raise Exception("The file path %s does not exist" % filepath)
            
            if self.ps:
                # - a number means returned (exit code), None means still running 
                dead = self.ps.poll() is not None 
                if dead:
                    logger.debug("No running process in the way, continuing..")
                else:
                    if force:
                        logger.debug("Forcing play, so killing existing process..")
                        try:
                            self.ps.kill()
                            del self.ps
                        except:
                            logger.error("Error killing process and deleting subprocess")
                            logger.error(str(sys.exc_info()[1]))
                    else:
                        response['message'] = "Running process, not forcing.. returning"
            
            self.player.play(filepath)
            self.player.set_volume()
            
            def call_callback(returncode=0, out='', err=''):
                callback_response = {'success': returncode == 0, 'message': out if returncode == 0 else err}
                requests.post(callback_url, headers={'content-type': 'application/json'}, data=json.dumps(callback_response))
                self.player.current_command = None 
                
            def run_in_thread():#, command, force):
                '''Thread target'''
                out = None 
                err = None 
                logger.info("Waiting for self.ps..")
                returncode = self.ps.wait()
                #(out, err) = self.ps.communicate(None)
                #returncode = self.ps.returncode
                logger.info("returncode: %s" % returncode)
                # logger.info(out)
                # logger.info(err)
                # logger.info("ps is done, calling on_exit()")
                # logger.info("ps.stdout:")
                # logger.info(self.ps.stdout)
                # logger.info("ps.stderr:")
                # logger.info(self.ps.stderr)
                call_callback(returncode=returncode, out=out, err=err)
                return

            self.current_thread = threading.Thread(target=run_in_thread) #, command, force))
            self.current_thread.start()
            
            #self.current_thread = self.popenAndCall(call_callback)#, command, force)
            # self.ps = subprocess.Popen(command, shell=do_shell, stdin=subprocess.PIPE, stdout=self.f_outw, stderr=self.f_errw)

            '''
            Playing /mnt/music/Unknown artist/George Harrison/Unknown album (6-1-2014 11-17-24 PM)_03_Track 3.mp3.
            libavformat version 55.33.100 (internal)
            Audio only file format detected.
            Clip info:
             Title: Track 3
             Artist:
             Album: Unknown album (6/1/2014 11:17:
             Year:
             Comment:
             Track: 3
             Genre: Unknown
            '''
            
            response['success'] = True 
            
        except Exception as e:

            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])            
            response['message'] = str(sys.exc_info()[1])

        logger.debug("Returning from play call")
        
        return response

    # def popenAndCall(self, on_exit):#, command, force):
    #     """
    #     Runs the given args in a subprocess.Popen, and then calls the function
    #     on_exit when the subprocess completes.
    #     on_exit is a callable object, and command is a list/tuple of args that
    #     would give to subprocess.Popen.
    #     """
    # 
    #     def run_in_thread(on_exit):#, command, force):
    #         '''Thread target'''
    #         logger.info("Waiting for self.ps..")
    #         wait_result = self.ps.wait()
    #         #(out, err) = self.ps.communicate(None)
    #         logger.info(wait_result)
    #         # logger.info(out)
    #         # logger.info(err)
    #         logger.info("ps is done, calling on_exit()")
    #         on_exit(wait_result)
    #         return
    # 
    #     thread = threading.Thread(target=run_in_thread, args=(on_exit,)) #, command, force))
    #     thread.start()
    # 
    #     return thread

    
        
    


    
    
        

    


if __name__ == "__main__":

    logger.debug("Creating option parser..")
    parser = OptionParser(usage='usage: %prog [options]')

    logger.debug("Adding options..")
    parser.add_option("-a", "--address", dest="address", default='127.0.0.1', help="IP address on which to listen")
    parser.add_option("-p", "--port", dest="port", default='9000', help="port on which to listen")

    logger.debug("Parsing args..")
    (options, args) = parser.parse_args()

    logger.debug("Creating MPPlayer..")
    m = MPPlayer()

    logger.debug("Creating XML RPC server..")
    s = SimpleXMLRPCServer((options.address, int(options.port)), allow_none=True)

    logger.debug("Registering MPPlayer with XML RPC server..")
    s.register_instance(m)

    logger.info("Serving forever on %s:%s.." % (options.address, options.port))
    s.serve_forever()  # not

    logger.debug("Served.")
