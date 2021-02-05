#!/usr/bin/env python3

import coloredlogs
import logging
coloredlogs.install(level='DEBUG', fmt='[ %(levelname)7s ] %(asctime)s %(name)s %(filename)12s:%(lineno)-4d %(message)s')

import os
import sys
import traceback
import time
import json
from xmlrpc.server import SimpleXMLRPCServer
from optparse import OptionParser
import requests
from wrappers import BaseWrapper, MPVWrapper, MPlayerWrapper
from health import PlayerHealth

PLAYER_LOG_LEVEL = os.getenv('BEATPLAYER_PLAYER_LOG_LEVEL', 'INFO')

logger_player = logging.getLogger(__name__)
logger_player.setLevel(level=logging._nameToLevel[PLAYER_LOG_LEVEL.upper()])

logger_urllib = logging.getLogger('urllib3')
logger_urllib.setLevel(level=logging.WARN)
        

class MPPlayer():
    
    player_clients = [MPVWrapper, MPlayerWrapper]
    player = None 
    health = None 
    server = False 

    def __init__(self, *args, **kwargs):
        
        self.server = kwargs['server'] if 'server' in kwargs else False 
        
        # self.f_outw = open("mplayer.out", "wb")
        # self.f_errw = open("mplayer.err", "wb")
        # 
        # self.f_outr = open("mplayer.out", "rb")
        # self.f_errr = open("mplayer.err", "rb")
        
        logger_player.info("Choosing player..")
        preferred_player = kwargs['player'] if 'player' in kwargs else None 
        for p in [ c for c in self.player_clients if c.executable_filename() == preferred_player or not preferred_player ]:
            if p.can_play():
                logger_player.info(" - %s can play - choosing" % p.__name__)
                self.player = BaseWrapper.getInstance(p)
                break 
            else:
                logger_player.info("  - %s cannot play" % p.__name__)
        
        if not self.player:
            self.player = BaseWrapper.getInstance()
            logger_player.warning("No suitable player could be found. BaseWrapper called without a wrapper type.")

        self.health = PlayerHealth()
    
    def _dispatch(self, method, params):
        # logger_player.debug("Attempting to dispatch %s" % method)
        modules = [self.player, self.health, self]
        f = None 
        response = None 
        for m in modules:
            try:
                # logger_player.debug("Looking for %s on %s" % (method, m.__class__.__name__))
                f = getattr(m, method)
                logger_player.debug("Dispatching %s on %s" % (method, m.__class__.__name__))
                response = f(*params)
            except AttributeError as ae:
                # logger_player.error(sys.exc_info()[0])
                logger_player.error(sys.exc_info()[1])
                # -- but try another one..
            except Exception as e:
                logger_player.error(sys.exc_info()[0])
                logger_player.error(sys.exc_info()[1])
                traceback.print_tb(sys.exc_info()[2])
                raise e
        if not f:
            raise Exception("Cannot dispatch %s: not found")
        return response
            
    # def logs(self):
    #     self.f_outr.seek(0)
    #     lines = list(self.f_outr)
    #     return lines

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
    #         logger_player.error(sys.exc_info())
    #         traceback.print_tb(sys.exc_info()[2])

    # def stop(self):
    #     response = {'success': False, 'message': '', 'data': {}}
    #     try:
    #         response = self.player.stop()
    #     except:
    #         response['message'] = str(sys.exc_info()[1])
    #     return response
    # 
    # def pause(self):
    #     response = {'success': False, 'message': '', 'data': {}}
    #     try:
    #         response = self.player.pause()
    #     except:
    #         response['message'] = str(sys.exc_info()[1])
    #     return response
    
    # def volume_up(self):
    #     response = {'success': False, 'message': '', 'data': {}}
    #     try:
    #         response = self.player.volume_up()
    #     except:
    #         response['message'] = str(sys.exc_info()[1])
    #     return response 
    # 
    # def volume_down(self):
    #     response = {'success': False, 'message': '', 'data': {}}
    #     try:
    #         response = self.player.volume_down()
    #     except:
    #         response['message'] = str(sys.exc_info()[1])
    #     return response 

    # def mute(self):
    #     response = {'success': False, 'message': '', 'data': {}}
    #     try:
    #         response = self.player.mute()
    #     except:
    #         response['message'] = str(sys.exc_info()[1])
    #     return responsecallback_url
    
    # def play(self, filepath, callback_url=None): #, force=False):#, match=None):
    # 
    #     response = {'success': False, 'message': '', 'data': {}}
    #     logger_player.debug("Playing %s" % filepath)
    # 
    #     try:
    # 
    #         response = self.player.play(filepath, callback_url)
    # 
    #         #t = self.popenAndCall(call_callback)#, command, force)
    #         # self.ps = subprocess.Popen(command, shell=do_shell, stdin=subprocess.PIPE, stdout=self.f_outw, stderr=self.f_errw)
    # 
    #         '''
    #         Playing /mnt/music/Unknown artist/George Harrison/Unknown album (6-1-2014 11-17-24 PM)_03_Track 3.mp3.
    #         libavformat version 55.33.100 (internal)
    #         Audio only file format detected.
    #         Clip info:
    #          Title: Track 3
    #          Artist:
    #          Album: Unknown album (6/1/2014 11:17:
    #          Year:
    #          Comment:
    #          Track: 3
    #          Genre: Unknown
    #         '''
    # 
    #         response['success'] = True 
    # 
    #     except Exception as e:
    # 
    #         logger_player.error(sys.exc_info()[0])
    #         logger_player.error(sys.exc_info()[1])
    #         traceback.print_tb(sys.exc_info()[2])            
    #         response['message'] = str(sys.exc_info()[1])
    # 
    #     return response

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
    #         logger_player.info("Waiting for self.ps..")
    #         wait_result = self.ps.wait()
    #         #(out, err) = self.ps.communicate(None)
    #         logger_player.info(wait_result)
    #         # logger_player.info(out)
    #         # logger_player.info(err)
    #         logger_player.info("ps is done, calling on_exit()")
    #         on_exit(wait_result)
    #         return
    # 
    #     thread = threading.Thread(target=run_in_thread, args=(on_exit,)) #, command, force))
    #     thread.start()
    # 
    #     return thread

if __name__ == "__main__":
    
    parser = OptionParser(usage='usage: %prog [options]')

    parser.add_option("-a", "--address", dest="address", default='0.0.0.0', help="IP address on which to listen")
    parser.add_option("-p", "--port", dest="port", default='9000', help="port on which to listen")
    parser.add_option("-t", "--smoke-test", action="store_true", dest="smoke_test", help="Smoke test")
    parser.add_option("-f", "--filepath", dest="filepath", help="Play file")
    parser.add_option("-e", "--player-executable", dest="executable", default='mpv', help="The executable program to play file")

    (options, args) = parser.parse_args()
    
    logger_player.debug("Options: %s" % options)
    
    if options.smoke_test:
        try:
            play_test_filepath = options.filepath if options.filepath else os.path.basename(sys.argv[0])
            logger_player.info("Running smoke test with %s playing %s" % (options.executable, play_test_filepath))
            m = MPPlayer(player=options.executable)
            m.play(filepath=play_test_filepath)
        except:
            logger_player.error(str(sys.exc_info()[0])) 
            logger_player.error(str(sys.exc_info()[1])) 
            traceback.print_tb(sys.exc_info()[2])
    elif options.filepath:
        try:
            m = MPPlayer(player=options.executable)
            result = m.play(filepath=options.filepath)
        except:
            logger_player.error(str(sys.exc_info()[0])) 
            logger_player.error(str(sys.exc_info()[1])) 
            traceback.print_tb(sys.exc_info()[2])
    else:

        logger_player.info("Creating XML RPC server..")
        s = SimpleXMLRPCServer((options.address, int(options.port)), allow_none=True)

        m = MPPlayer(server=True, player=options.executable)
        logger_player.info("Registering MPPlayer with XML RPC server..")
        s.register_instance(m)

        logger_player.info("Serving forever on %s:%s.." % (options.address, options.port))
        s.serve_forever()
