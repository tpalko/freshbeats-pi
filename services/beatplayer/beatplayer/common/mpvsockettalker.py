import sys
import socket 
import signal
import os
import logging 
import time 
import threading 
import random 
import json 
from contextlib import contextmanager 
import traceback 

logger = logging.getLogger(__name__)

class MpvSocketTalker():
    
    '''
    mst = MpvSocketTalker.getInstance("/tmp/mpv.sock")
    request_id = mst.async_send("command")
    response = mst.read(request_id)
    response = mst.send("command")
    '''
    
    watch_loop = True 
    __instance = None 
    response_queue = {}
    socket_file = None 
    watch_thread = None 
    lock = None 
    sigint = False 
        
    @staticmethod 
    def getInstance(socket_file):
        if MpvSocketTalker.__instance == None:
            MpvSocketTalker(socket_file=socket_file)
        return MpvSocketTalker.__instance 
    
    def __init__(self, *args, **kwargs):
        if MpvSocketTalker.__instance != None:
            raise Exception("Call MpvSocketTalker.getInstance for instance")
        else:
            if 'socket_file' not in kwargs:
                raise Exception("Required 'socket_file' not found in kwargs")
            self.lock = threading.Lock()
            self.socket_file = kwargs['socket_file']            
            self.watch_thread = threading.Thread(target=self._watch)
            self.watch_thread.start()
            MpvSocketTalker.__instance = self 
            signal.signal(signal.SIGINT, self._get_sigint_handler())
    
    def _get_sigint_handler(self):
        def handler(sig, frame):
            logger.warning("MpvSocketTalker handling SIGINT")
            self.sigint = True
            if self.watch_thread.is_alive():
                self.watch_thread.join(timeout=2)
                if self.watch_thread.is_alive():
                    logger.warning("   - %s timed out" % self.watch_thread.ident)
                else:
                    logger.warning("   - joined")
            else:
                logger.warning("   - not alive")
            sys.exit(0)
        return handler 
        
    def _connect(self, s):
        attempts = 0
        while not os.path.exists(self.socket_file):
            if attempts > 15:
                logger.warning("tried 15 times over 30 seconds to find %s, quitting" % self.socket_file)
                break
            else:
                logger.warning("%s does not exist.. waiting 2.." % self.socket_file)
                attempts += 1
                time.sleep(2)
        if os.path.exists(self.socket_file):
            attempts = 0
            data = ""
            while True:
                try:
                    attempts += 1
                    s.connect(self.socket_file)
                    s.settimeout(2)
                    logger.info("Connected to %s" % self.socket_file)
                    break 
                except:
                    logger.error("Failed connecting to %s" % self.socket_file)
                    break 
                    # if attempts > 10:
                    #     raise Exception("Could not connect to %s, quitting" % self.socket_file)
                    # time.sleep(1)
    
    @contextmanager
    def socket(self):
        watch_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._connect(watch_socket)
        try:
            yield watch_socket 
        except:
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
        finally:
            watch_socket.close()
            
    def _new_request_id(self, request_id=None):
        while request_id is None or request_id in self.response_queue:
            request_id = random.choice(range(999))
        return request_id 
            
    def _send(self, command):
        
        request_id = None 
        
        with self.socket() as send_socket:
            if 'request_id' in command:
                request_id = command['request_id']
            else:
                request_id = self._new_request_id()
                command['request_id'] = request_id
            send_socket.send(bytes(json.dumps(command) + '\n', encoding='utf8'))
        
        return request_id
    
    def _read(self, request_id):
        while True:
            self.lock.acquire()
            if request_id in self.response_queue:
                if len(self.response_queue[request_id]) > 0:
                    response = self.response_queue[request_id][0]
                    del self.response_queue[request_id][0]
                    return response
            self.lock.release()
            time.sleep(1)
                
    def async_send(self, command):
        return self._send(command)
        
    def send(self, command):
        return self._read(self._send(command))
    
    def read(self, request_id):
        return self._read(request_id)
        
    def stop_watch(self):
        self.watch_loop = False 
        
    def _watch(self):
        with self.socket() as watch_socket:
            blanks = 0
            self.data = ""
            logger.debug("Looping socket recv for any output")
            while self.watch_loop and self.sigint:
                try:
                    received_raw = watch_socket.recv(1024)
                    received = received_raw.decode()
                    logger.debug("Received from socket: %s" % received)
                    self.data = "%s%s" % (self.data, received)    
                    if self.data == "":
                        time.sleep(1)
                    logger.debug(" - socket response: %s" % self.data)
                    for n in [ json.reads(d) for d in self.data.split('\n') if d ]:
                        if 'request_id' in n:
                            request_id = n['request_id']
                            self.lock.acquire()
                            if request_id not in self.response_queue:
                                self.response_queue[request_id] = []
                            self.response_queue[request_id].append(n['data'])
                            self.lock.release()
                        if 'event' in n:
                            logger.info("Socket event: %s" % n['event'])
                    self.data = ""
                except:
                    logger.error(sys.exc_info()[0])
                    logger.error(sys.exc_info()[1])
                    traceback.print_tb(sys.exc_info()[2])
                    time.sleep(1)
        
