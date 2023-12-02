#!/usr/bin/env python3

import cowpy
import sys

# import colorlog
# import logging
import os

import traceback
import time
import json
from xmlrpc.server import SimpleXMLRPCServer
from optparse import OptionParser
import requests
from beatplayer.basewrapper import BaseWrapper
from beatplayer.health import PlayerHealth

# import django
# sys.path.append(os.path.join(os.path.dirname(__file__), '../../../webapp'))
# os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'
# django.setup()

PLAYER_LOG_LEVEL = os.getenv('BEATPLAYER_PLAYER_LOG_LEVEL', 'DEBUG')

logger_player = cowpy.getLogger(__name__)

# print(f'creating logger as {__name__}')
# logger_player = logging.getLogger(__name__)

# for h in logger_player.handlers:
#     print("Removing handler: %s" % h)
#     logger_player.removeHandler(h)

# logger_player.setLevel(level=logging._nameToLevel[PLAYER_LOG_LEVEL.upper()])
# 
# handler = colorlog.StreamHandler()
# MAX_LEVEL_NAME = max([ len(l) for l in logging._nameToLevel.keys() ])
# FORMATTER_STRING = f'%(log_color)s[ %(levelname){MAX_LEVEL_NAME}s ] %(asctime)s %(filename)14s:%(lineno)-4d %(message)s'
# handler.setFormatter(colorlog.ColoredFormatter(FORMATTER_STRING))
# logger_player.addHandler(handler)
# 
# logger_urllib = colorlog.getLogger('urllib3')
# logger_urllib.setLevel(level=logging.WARN)

class MPPlayer():
    
    player = None 
    health = None 

    def __init__(self, *args, **kwargs):
        
        self.player = BaseWrapper.getInstance(player_type=kwargs['player'] if 'player' in kwargs else None)
        self.health = PlayerHealth(sigint_callback=self.player.stop)

    def serve(self):

        host = '0.0.0.0'
        beatplayer_port = int(os.getenv('BEATPLAYER_PORT', 9000))

        logger_player.debug("Creating XML RPC server..")
        rpc_server = SimpleXMLRPCServer((host, beatplayer_port), allow_none=True)

        logger_player.debug("Registering MPPlayer with XML RPC server..")
        rpc_server.register_instance(self)
        
        logger_player.debug(f'Serving forever on {host}:{beatplayer_port}..')
        rpc_server.serve_forever()

    def _dispatch(self, method, params):
        logger_player.debug("Attempting to dispatch %s / %s" % (method, params))
        modules = [self.player, self.health, self]
        response = None 
        for m in [ m for m in modules if hasattr(m, method) ]:
            try:
                f = getattr(m, method)
                logger_player.debug("Dispatching %s on %s" % (method, m.__class__.__name__))
                response = f(*params)
            except Exception as e:
                logger_player.error(sys.exc_info()[0])
                logger_player.error(sys.exc_info()[1])
                traceback.print_tb(sys.exc_info()[2])
                raise e 

        return response

# if __name__ == "__main__":
    
#     parser = OptionParser(usage='usage: %prog [options]')

#     parser.add_option("-a", "--address", dest="address", default='0.0.0.0', help="IP address on which to listen")
#     parser.add_option("-p", "--port", dest="port", default='9000', help="port on which to listen")
#     parser.add_option("-t", "--smoke-test", action="store_true", dest="smoke_test", help="Smoke test")
#     parser.add_option("-f", "--filepath", dest="filepath", help="Play file")
#     parser.add_option("-e", "--player-executable", dest="executable", default='mpv', help="The executable program to play file")

#     (options, args) = parser.parse_args()
    
#     logger_player.debug("Options: %s" % options)
    
#     if options.smoke_test:
#         try:
#             play_test_filepath = options.filepath if options.filepath else os.path.basename(sys.argv[0])
#             logger_player.info("Running smoke test with %s playing %s" % (options.executable, play_test_filepath))
#             m = MPPlayer(player=options.executable)
#             m.play(filepath=play_test_filepath)
#         except:
#             logger_player.error(str(sys.exc_info()[0])) 
#             logger_player.error(str(sys.exc_info()[1])) 
#             traceback.print_tb(sys.exc_info()[2])
#     elif options.filepath:
#         try:
#             m = MPPlayer(player=options.executable)
#             result = m.play(filepath=options.filepath)
#         except:
#             logger_player.error(str(sys.exc_info()[0])) 
#             logger_player.error(str(sys.exc_info()[1])) 
#             traceback.print_tb(sys.exc_info()[2])
#     else:

#         p = MPPlayer(player='mpv')
#         p.serve()
