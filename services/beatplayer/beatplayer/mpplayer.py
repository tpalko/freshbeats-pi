#!/usr/bin/env python

import os
import sys
import traceback
import time
import json
try: #3
    from xmlrpc.server import SimpleXMLRPCServer
except: #2
    from SimpleXMLRPCServer import SimpleXMLRPCServer
import logging
from optparse import OptionParser
import requests
import threading
from wrappers import MPVWrapper, MPlayerWrapper

BEATPLAYER_DEFAULT_VOLUME = 90
BEATPLAYER_INITIAL_VOLUME = int(os.getenv('BEATPLAYER_INITIAL_VOLUME', BEATPLAYER_DEFAULT_VOLUME))

PLAYER_LOG_LEVEL = os.getenv('BEATPLAYER_PLAYER_LOG_LEVEL', 'INFO')

logging.basicConfig(level=logging.WARN)

logger_player = logging.getLogger('mpplayer.player')
logger_player.setLevel(level=logging._nameToLevel[PLAYER_LOG_LEVEL.upper()])

logger_urllib = logging.getLogger('urllib3')
logger_urllib.setLevel(level=logging.WARN)
 
class MPPlayer():
    
    player_clients = [MPVWrapper, MPlayerWrapper]
    player = None 
    server = False 
    
    play_thread = None 
    health = None 

    def __init__(self, *args, **kwargs):
        
        self.server = kwargs['server'] if 'server' in kwargs else False 
        
        self.f_outw = open("mplayer.out", "wb")
        self.f_errw = open("mplayer.err", "wb")

        self.f_outr = open("mplayer.out", "rb")
        self.f_errr = open("mplayer.err", "rb")

        self.music_folder = os.getenv('BEATPLAYER_MUSIC_FOLDER', '/mnt/music')
        
        logger_player.info("Choosing player..")
        preferred_player = kwargs['player'] if 'player' in kwargs else None 
        for p in self.player_clients:
            i = p()
            player_name = i.__class__.__name__
            if i.can_play():
                logger_player.info("  - %s can play" % player_name)
                self.player = i
                if preferred_player and i.player_path == preferred_player:
                    break 
            else:
                logger_player.info("  - %s cannot play" % player_name)
        
        logger_player.info("  - %s chosen (%s)" % (self.player.__class__.__name__, self.player.player_path))
        
        if not self.player:
            raise Exception("No suitable player exists")   
        
        logger_player.info("music folder: %s" % self.music_folder)

        self.muted = False
        
        self.health = PlayerHealth()

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
    #         logger_player.error(sys.exc_info())
    #         traceback.print_tb(sys.exc_info()[2])

    def stop(self):
        response = {'success': False, 'message': '', 'data': {}}
        try:
            response = self.player.stop()
        except:
            response['message'] = str(sys.exc_info()[1])
        return response
    
    def pause(self):
        response = {'success': False, 'message': '', 'data': {}}
        try:
            response = self.player.pause()
        except:
            response['message'] = str(sys.exc_info()[1])
        return response
    
    def volume_up(self):
        response = {'success': False, 'message': '', 'data': {}}
        try:
            response = self.player.volume_up()
        except:
            response['message'] = str(sys.exc_info()[1])
        return response 
    
    def volume_down(self):
        response = {'success': False, 'message': '', 'data': {}}
        try:
            response = self.player.volume_down()
        except:
            response['message'] = str(sys.exc_info()[1])
        return response 

    def mute(self):
        response = {'success': False, 'message': '', 'data': {}}
        try:
            response = self.player.mute()
        except:
            response['message'] = str(sys.exc_info()[1])
        return response
        
    def play(self, filepath, callback_url=None): #, force=False):#, match=None):
        
        response = {'success': False, 'message': '', 'data': {}}
        logger_player.debug("Playing %s" % filepath)
            
        try:

            if not os.path.exists(filepath):
                raise Exception("The file path %s does not exist" % filepath)
            
            response = self.player.play(filepath)
            self.player.set_volume()
            
            def run_in_thread(callback_url):#, command, force):
                '''Thread target'''
                logger_player.info("Waiting for self.ps..")                
                
                if callback_url:
                    process_dead = False 
                    int_resp = {'success': True, 'message': '', 'data': {'complete': False}} 
                    '''
                    order matters:
                        read - post - break (don't lose data)
                        check - read - break (break on what we knew before the read)
                        start - break - sleep (so we don't sleep unnecessarily)
                    '''
                    while True:
                        try:
                            if self.player.ps.poll() is not None:
                                logger_player.debug('player process is dead')
                                process_dead = True 
                            else:
                                logger_player.debug('player process is running (%s)' % self.player.ps.pid)
                            logger_player.debug(' '.join(self.player.current_command) if self.player.current_command else None)
                            logger_player.debug("reading from player stdout..")
                            lines = []
                            next_line = self.player.ps.stdout.readline()
                            while next_line != '' and 'Broken pipe' not in next_line:
                                logger_player.debug(next_line)
                                lines.append(next_line)
                                time.sleep(0.3)
                                logger_player.debug(dir(self.player.ps))
                                logger_player.debug(dir(self.player.ps.stdout))
                                next_line = self.player.ps.stdout.readline()
                                logger_player.debug("line was read..")
                            logger_player.debug("done reading")
                            int_resp['message'] = '\n'.join(lines)
                            
                            if len(int_resp['message']) > 0:
                                logger_player.debug('intermittent response has a message: %s' % int_resp["message"])
                                for line in lines:
                                    logger_player.debug("STDOUT: %s" % line)
                                requests.post(callback_url, headers={'content-type': 'application/json'}, data=json.dumps(int_resp))
                            else:
                                logger_player.debug("stdout is empty")
                            
                            if len(int_resp['message']) > 0:
                                int_resp['message'] = ''
                            else:
                                time.sleep(1)
                        except:
                            logger_player.error(sys.exc_info()[0])
                            logger_player.error(sys.exc_info()[1])
                            traceback.print_tb(sys.exc_info()[2])
                        finally:
                           if process_dead:
                               logger_player.debug("process is dead, exiting stdout while loop")
                               break
                logger_player.debug("Waiting on player process..")
                returncode = self.player.ps.wait()
                (out, err) = self.player.ps.communicate(None)
                logger_player.debug("returncode: %s" % returncode)
                logger_player.debug("out: %s" % out)
                logger_player.debug("err: %s" % err)
                if callback_url:
                    callback_response = {'success': returncode == 0, 'message': '', 'data': {'complete': True, 'out': out, 'err': err}}
                    requests.post(callback_url, headers={'content-type': 'application/json'}, data=json.dumps(callback_response))
                self.player.current_command = None                 
                return

            logger_player.info("New thread to handle play: %s" % filepath)
            self.play_thread = threading.Thread(target=run_in_thread, args=(callback_url,)) #, command, force))
            self.play_thread.start()
            
            if not self.server:
                logger.player.info("Not running in server mode. Joining thread when done.")
                self.play_thread.join()
            
            #t = self.popenAndCall(call_callback)#, command, force)
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

            logger_player.error(sys.exc_info()[0])
            logger_player.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])            
            response['message'] = str(sys.exc_info()[1])

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

    logger_player.debug("Adding options..")
    parser.add_option("-a", "--address", dest="address", default='0.0.0.0', help="IP address on which to listen")
    parser.add_option("-p", "--port", dest="port", default='9000', help="port on which to listen")
    parser.add_option("-t", "--smoke-test", action="store_true", dest="smoke_test", help="Smoke test")
    parser.add_option("-f", "--filepath", dest="filepath", help="Play file")
    parser.add_option("-e", "--player-executable", dest="executable", default='mpv', help="The executable program to play file")

    (options, args) = parser.parse_args()
    
    logger_player.debug("Options:")
    logger_player.debug(options)
    
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
        s.register_instance(m.health)

        logger_player.info("Serving forever on %s:%s.." % (options.address, options.port))
        s.serve_forever()
