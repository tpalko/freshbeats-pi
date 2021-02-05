#!/usr/bin/env python 

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

# %(name)-17s
logging.basicConfig(
    level=logging.WARN,
    format='[ %(levelname)7s ] %(asctime)s %(name)s %(filename)s:%(lineno)-4d %(message)s'
)

logger = logging.getLogger(__name__)

class MpvSocketTalker():
    
    '''
    mst = MpvSocketTalker.getInstance("/tmp/mpv.sock")
    request_id = mst.async_send("command")
    response = mst.read(request_id)
    response = mst.send("command")
    '''
    
    sendread_logger = None 
    watch_logger = None 
    watch_loop = True 
    __instance = None 
    response_queue = {}
    socket_file = None 
    watch_thread = None 
    _queue_lock = None 
    _socket_lock = None 
    sigint = False 
    _socket = None 
    data = ""
        
    @staticmethod 
    def getInstance(socket_file, log_level='INFO'):
        if MpvSocketTalker.__instance == None:
            MpvSocketTalker(socket_file=socket_file, log_level=log_level)
        return MpvSocketTalker.__instance 
    
    def __init__(self, *args, **kwargs):
        if MpvSocketTalker.__instance != None:
            raise Exception("Call MpvSocketTalker.getInstance for instance")
        else:
            if 'socket_file' not in kwargs:
                raise Exception("Required 'socket_file' not found in kwargs")
            if 'log_level' in kwargs:                
                logger.setLevel(level=logging._nameToLevel[kwargs['log_level'].upper()])
            
            self._configure_logging()
            
            logger.info("Creating %s singleton" % self.__class__.__name__)
            self.socket_file = kwargs['socket_file']    
            self._queue_lock = threading.Lock()    
            self._socket_lock = threading.Lock()        
            logger.info("  - socket file: %s" % self.socket_file)
            #signal.signal(signal.SIGINT, self._get_sigint_handler())
            MpvSocketTalker.__instance = self 
    
    def _configure_logging(self):
        
        #coloredlogs.install(level='DEBUG', fmt='[ %(levelname)7s ] %(asctime)s %(name)s %(filename)12s:%(lineno)-4d %(message)s')
        #fmt = logging.Formatter('[ %(levelname)7s ] %(asctime)s %(name)s %(filename)12s:%(lineno)-4d %(message)s')
        
        self.sendread_logger = logging.getLogger("%s.sendread" % __name__)
        for handler in self.sendread_logger.handlers:
            logger.info("Removing %s from sendread logger" % (handler))
            self.sendread_logger.removeHandler(handler)
        sendread_handler = logging.FileHandler('mpvsockettalker_sendread.log')
        sendread_handler.propagate = False 
        #sendread_handler.setFormatter(fmt)
        # sendread_handler.setLevel(level=logging.DEBUG)
        logger.info("Adding %s to sendread logger" % (sendread_handler))
        self.sendread_logger.addHandler(sendread_handler)
        # self.sendread_logger.setLevel(level=logging.DEBUG)

        self.watch_logger = logging.getLogger("%s.watch" % __name__)
        for handler in self.watch_logger.handlers:
            logger.info("Removing %s from watch logger" % (handler))
            self.watch_logger.removeHandler(handler)
        watch_handler = logging.FileHandler('mpvsockettalker_watch.log')
        watch_handler.propagate = False 
        #watch_handler.setFormatter(fmt)
        # watch_handler.setLevel(level=logging.DEBUG)
        logger.info("Adding %s to watch logger" % (watch_handler))
        self.watch_logger.addHandler(watch_handler)
        # self.watch_logger.setLevel(level=logging.DEBUG)
        
    def _get_sigint_handler(self):
        def handler(sig, frame):
            logger.warning("MpvSocketTalker handling SIGINT")
            logger.warning("Setting sigint of %s True" % id(self))
            self.sigint = True
            logger.warning("Joining watch thread..")
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
        
    # def _connect(self, s):
    #     attempts = 0
    #     while not os.path.exists(self.socket_file):
    #         if attempts > 15:
    #             logger.warning("tried 15 times over 30 seconds to find %s, quitting" % self.socket_file)
    #             break
    #         else:
    #             logger.warning("%s does not exist.. waiting 2.." % self.socket_file)
    #             attempts += 1
    #             time.sleep(2)
    #     if os.path.exists(self.socket_file):
    #         attempts = 0
    #         data = ""
    #         while True:
    #             try:
    #                 attempts += 1
    #                 s.connect(self.socket_file)
    #                 s.settimeout(2)
    #                 logger.info("Connected to %s" % self.socket_file)
    #                 break 
    #             except:
    #                 logger.error("Failed connecting to %s" % self.socket_file)
    #                 break 
                    # if attempts > 10:
                    #     raise Exception("Could not connect to %s, quitting" % self.socket_file)
                    # time.sleep(1)
    
    @contextmanager
    def socket(self):        
        caller = traceback.format_stack()[-3].split(' ')[7].replace('\n', '')
        try:
            logger.debug("SOCKET: Socket lock desired for %s" % caller)
            self._socket_lock.acquire()
            if not self._socket:
                logger.debug("SOCKET: creating new socket")
                self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._socket.connect(self.socket_file)
                self._socket.settimeout(5)
            else:
                logger.debug("SOCKET: recycling socket")
            # self._connect(s)
            # logger.info(dir(s))
            logger.debug("SOCKET: Yielding socket to caller %s" % caller)
            yield self._socket 
        except Exception as e:
            logger.error("Nonifying socket: %s %s" % (sys.exc_info()[0], sys.exc_info()[1]))
            self._socket = None 
            raise e 
            # logger.error(sys.exc_info()[0])
            # logger.error(sys.exc_info()[1])
            # traceback.print_tb(sys.exc_info()[2])
        finally:
            #self._socket.close()
            self._socket_lock.release()
            logger.debug("SOCKET: Socket lock released by %s" % caller)
            
    @contextmanager
    def queue_lock(self):
        caller = traceback.format_stack()[-3].split(' ')[7].replace('\n', '')
        try:
            logger.debug("QUEUE LOCK: %s wants to acquire response queue lock.." % caller)
            self._queue_lock.acquire()
            logger.debug("QUEUE LOCK: %s has acquired response queue lock" % caller)
            yield self.response_queue
        except:
            logger.error("Exception during lock yield")
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
        finally:
            logger.debug("QUEUE LOCK: response queue: %s" % json.dumps({ r: self.response_queue[r] for r in self.response_queue if len(self.response_queue[r]) > 0 }, indent=4))
            self._queue_lock.release()
            logger.debug("QUEUE LOCK: %s has released response queue lock" % caller)
            
    def _new_request_id(self, request_id=None):
        with self.queue_lock() as response_queue:
            while request_id is None or request_id in response_queue:
                request_id = random.choice(range(999))
                # logger.debug("request_id chosen: %s" % request_id)
        # logger.debug("request_id accepted: %s" % request_id)
        return request_id 
            
    def _send(self, command):
        
        request_id = None 
        self.sendread_logger.debug("SEND: command '%s'" % command)
        with self.socket() as send_socket:
            if 'request_id' in command:
                request_id = command['request_id']
                self.sendread_logger.debug("  - SEND: request_id found on command: %s" % (request_id))
            else:
                request_id = self._new_request_id()
                command['request_id'] = request_id
                self.sendread_logger.debug("  - SEND: request_id acquired: %s" % (request_id))
            send_result = send_socket.send(bytes(json.dumps(command) + '\n', encoding='utf8'))
            #send_recv_raw = send_socket.recv(1024)
            # self.sendread_logger.debug("  - SEND: Command sent to socket: %s" % command)
            #self.sendread_logger.debug("  - SEND: Recv from send (%s): %s" % (send_result, send_recv_raw.decode()))
        
        return request_id
    
    def _read(self, request_id, multi_response=False):
        starts = 0
        self.sendread_logger.debug("READ: Looking for socket responses, request_id: %s" % request_id)
        response = [] if multi_response else None  
        while True:
            # -- watch thread is the thing that populates the response queue 
            if not self.watch_thread or not self.watch_thread.is_alive():
                if starts == 0:
                    self.sendread_logger.info("READ: Watch thread starting for read (request_id=%s)" % request_id)
                    self.watch_thread = threading.Thread(target=self._watch, args=(self,))
                    self.watch_thread.start()
                    starts += 1
                else:
                    self.sendread_logger.warning("READ: Watch thread dead twice since read request")
                    break 
            with self.queue_lock() as response_queue:
                # self.sendread_logger.debug("  - READ: in response queue lock looking for request_id: %s" % request_id)
                if request_id in response_queue:
                    if multi_response:
                        response = response_queue[request_id]
                        del response_queue[request_id]
                        self.sendread_logger.debug("  - READ: found response for request_id %s: %s" % (request_id, response))
                    else:
                        if len(response_queue[request_id]) > 0:
                            response = response_queue[request_id][0]
                            del response_queue[request_id][0]
                            self.sendread_logger.debug("  - READ: found response for request_id %s: %s" % (request_id, response))
                        else:
                            self.sendread_logger.warning("  - READ: request ID %s found on queue with no responses" % request_id)
                    break 
            self.sendread_logger.debug("  - READ: no response for request_id: %s" % request_id)
            time.sleep(1)
        return response 
                
    def async_send(self, command):
        return self._send(command)
        
    def send(self, command, multi_response=False):
        return self._read(self._send(command), multi_response=multi_response)
    
    def read(self, request_id, multi_response=True):
        return self._read(request_id, multi_response=multi_response)
    
    def _recv_socket_output(self):
        received_raw = ""
        with self.socket() as watch_socket:
            received_raw = watch_socket.recv(1024)
        self.watch_logger.debug("Data: '%s'" % self.data)
        self.watch_logger.debug("Raw output: %s" % received_raw)
        self.data = "%s%s" % (self.data, received_raw.decode())
        self.watch_logger.debug("  - WATCH: socket cumulative response: %s" % self.data)
        
    def _output_into_queue(self):
        for n in [ json.loads(d) for d in self.data.split('\n') if d ]:
            if 'request_id' in n:
                request_id = n['request_id']
                with self.queue_lock() as response_queue:
                    if request_id not in response_queue:
                        response_queue[request_id] = []
                    response_queue[request_id].append(n['data'])
            if 'event' in n:
                self.watch_logger.info("Socket event: %s" % n['event'])
    
    def _watch(self, parent):
        fails = 0
        self.data = ""
        while not parent.sigint and fails < 3:
            self.watch_logger.warning("WATCH: Top of watch loop with %s fails and %s SIGINT is %s.." % (fails, id(parent), parent.sigint))
            try:
                # blanks = 0
                self._recv_socket_output()
                # -- {'data': '{"event":"tracks-changed"}\n{"event":"end-file"}\n', 'success': True, 'message': ''}
                # --{'data': '{"data":false,"error":"success"}\n{"event":"audio-reconfig"}\n{"event":"tracks-changed"}\n{"event":"end-file"}\n', 'success': True, 'message': ''}
                self._output_into_queue()
                # self.watch_logger.debug("  - WATCH: response queue: %s" % self.response_queue)
                if self.data == "":
                    # self.watch_logger.debug("  - WATCH: sleeping")
                    time.sleep(1)
                self.data = ""
            except ConnectionRefusedError as cre:
                fails += 1
                self.watch_logger.error("Watch loop failed..")
                self.watch_logger.error(sys.exc_info()[0])
                self.watch_logger.error(sys.exc_info()[1])
                traceback.print_tb(sys.exc_info()[2])
                time.sleep(1)
            except:
                fails += 1
                self.watch_logger.error("Watch loop failed..")
                self.watch_logger.error(sys.exc_info()[0])
                self.watch_logger.error(sys.exc_info()[1])
                traceback.print_tb(sys.exc_info()[2])
                time.sleep(1)
        self.watch_logger.info("Watch loop exiting. SIGINT: %s, Fails: %s" % (parent.sigint, fails))
