#!/usr/bin/env python3

import cowpy
import os
import sys 
import time
import subprocess
import traceback
from threading import RLock 

from abc import ABCMeta, abstractmethod
from beatplayer.common.processmonitor import ProcessMonitor
from beatplayer.common.lists import Fifo 

# import django
# sys.path.append(os.path.join(os.path.dirname(__file__), '../../../webapp'))
# os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'
# django.setup()

BEATPLAYER_INITIAL_VOLUME_DEFAULT = 90
BEATPLAYER_HOST_MUSIC_FOLDER_DEFAULT = '/mnt/music'

class BaseWrapper():
    
    __metaclass__ = ABCMeta
    __instance = None 
    __logger = None 
    
    volume = None 
    music_folder = None     
    
    ps = None 
    
    muted = False # -- subclasses must manage this state 
    paused = False # - mpv works on a toggle, as opposed to mplayer, which needs not track this state 
    current_command = None 
    logger = None 
    lock = None 

    _command_queue = None 
    
    @abstractmethod
    def play(self, body, query):
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
    def _command_generator(self, url, filepath):
        pass 
    
    @abstractmethod
    def _init(self):
        pass 
    
    @staticmethod 
    def static_logger():
        if not BaseWrapper.__logger:
            BaseWrapper.__logger = cowpy.getLogger(name=__name__)
        return BaseWrapper.__logger

    @staticmethod 
    def getInstance(player_type=None, logger=None):

        if not logger:
            logger = BaseWrapper.static_logger()

        logger.debug('Getting player instance..')
        if BaseWrapper.__instance == None:            
            BaseWrapper.choose_player(player_type)()

        return BaseWrapper.__instance 

    @staticmethod 
    def choose_player(preferred_player_name=None):
        
        BaseWrapper.static_logger().info(f'Choosing player.. ({preferred_player_name} preferred)')
        
        if not preferred_player_name:
            preferred_player_name = os.getenv('BEATPLAYER_PREFERRED_PLAYER_NAME')
        beatplayer_wrapper_folder = os.getenv('BEATPLAYER_WRAPPER_FOLDER')

        import glob 
        import importlib 

        player_clients = []
        
        potential_wrappers = [ f for f in glob.glob(f'{beatplayer_wrapper_folder}/*.py') if not f.endswith('__init__.py') ]
        BaseWrapper.static_logger().debug(f'Found {len(potential_wrappers)} potential wrappers in {os.path.realpath(beatplayer_wrapper_folder)}/*.py')
        for wrapper_file in potential_wrappers:
            BaseWrapper.static_logger().debug(f'Examining potential wrapper {wrapper_file}')
            # module_name = wrapper_file.replace('.py', '').replace('/', '.')
            module_name = ".".join(wrapper_file.replace('.py', '').replace('.', '').split('/'))
            module_name = module_name[1:] if module_name[0] == '.' else module_name
            BaseWrapper.static_logger().debug(f'Importing {module_name}')
            module = importlib.import_module(module_name)
            player_clients.append(module)
            
        players_by_exec = { c.main.executable_filename(): c.main for c in player_clients if c.main.can_play() }
        chosen_player = None 
        
        if preferred_player_name and preferred_player_name in players_by_exec:
            BaseWrapper.static_logger().info(f'Preferred player chosen: {preferred_player_name}')
            chosen_player = preferred_player_name
        elif len(players_by_exec) > 0:
            chosen_player = list(players_by_exec.keys())[0]
        else:
            BaseWrapper.static_logger().warning("No suitable player could be found. BaseWrapper called without a wrapper type.")
        
        BaseWrapper.static_logger().info(f'Player chosen: {chosen_player}')

        return players_by_exec[chosen_player] if chosen_player else BaseWrapper
        
    def __init__(self, *args, **kwargs):

        if BaseWrapper.__instance != None:
            raise Exception("Already exists!")

        self.logger = BaseWrapper.static_logger()
        
        self.logger.info("Creating BaseWrapper/%s singleton" % self.__class__.__name__)
        
        self.volume = int(os.getenv('BEATPLAYER_INITIAL_VOLUME', BEATPLAYER_INITIAL_VOLUME_DEFAULT))
        self.music_folder = os.getenv('BEATPLAYER_HOST_MUSIC_FOLDER', BEATPLAYER_HOST_MUSIC_FOLDER_DEFAULT)

        self.logger.info("  - music folder: %s" % self.music_folder)            
        self.logger.info("  - volume: %s" % self.volume)

        self._command_queue = Fifo()
        self.lock = RLock()

        self._init()

        BaseWrapper.__instance = self 
    
    def issue_command(self, url, filepath, callback_url, agent_base_url):

        self.lock.acquire()
        
        (url, filepath, callback_url, agent_base_url,) = self._command_queue.apush((url, filepath, callback_url, agent_base_url,))

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
                process_monitor.process(self.ps, callback_url, agent_base_url)
                
                self.current_command = command 
                self.logger.debug(' '.join(self.current_command) if self.current_command else None)
                response['success'] = True 
            except:
                response['message'] = str(sys.exc_info()[1])
                self.logger.error(response['message'])
                self.logger.error(sys.exc_info()[0])
                traceback.print_tb(sys.exc_info()[2])
        
        self.lock.release()
        
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

    @classmethod
    def can_play(cls):
        result = False 
        try:
            ps = subprocess.Popen(["which", cls.executable_filename()], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = ps.wait() == 0
        except:
            BaseWrapper.static_logger().error(sys.exc_info()[0])
            BaseWrapper.static_logger().error(sys.exc_info()[1])                        
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
        
    