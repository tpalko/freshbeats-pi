#!/usr/bin/env python3

import cowpy
import os
import sys 
# import logging 
# import colorlog
import time 
import json 
import requests 
import threading 
import traceback 
from datetime import datetime 

# logging.basicConfig(
#     level=logging.WARN,
#     format='[ %(levelname)7s ] %(asctime)s %(name)-17s %(filename)s:%(lineno)-4d %(message)s'
# )
#f_handler = logging.FileHandler(filename='processmonitor.log', mode='a')
# import django
# sys.path.append(os.path.join(os.path.dirname(__file__), '../webapp'))
# os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'
# django.setup()

# print(f'creating logger as {__name__}')


#logger.addHandler(f_handler)
# handler = colorlog.StreamHandler()
# handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s[ %(levelname)7s ] %(asctime)s %(filename)12s:%(lineno)-4d %(message)s'))
# logger.addHandler(handler)

class ProcessMonitor():
    
    __instance = None 
    
    monitor_thread = None     
    last_activity = None 
    lines = None 
    
    ps = None 

    logger = None 
    
    process_dead = True
    let_thread_die = True 
    report_complete = True
    
    @staticmethod
    def getInstance():
        if ProcessMonitor.__instance is None:
            ProcessMonitor()
        return ProcessMonitor.__instance
    
    def __init__(self, *args, **kwargs):
        if ProcessMonitor.__instance is not None:
            raise Exception("Call ProcessMonitor.getInstance()")
        self.logger = cowpy.getLogger()
        ProcessMonitor.__instance = self
    
    def read_stream(self):
        while self.read_loop:
            self.lines.append(self.ps.stdout.readline())
            time.sleep(0.3)
    
    def _post_callback_url(self, data):
        response = None 
        if self.callback_url:
            self.logger.debug("Posting to %s.." % (self.callback_url))
            response = requests.post(self.callback_url, headers={'content-type': 'application/json'}, data=json.dumps(data))
            self.logger.debug("Response (%s): %s" %(response.status_code if response else "no response", json.dumps(data, indent=4)))
        else:
            self.logger.debug("Not posting to %s (no callback_url)" % (self.callback_url))
        return response 
        
    def report_stream(self):#, command, force):
        
        callback_data = {
            'success': True, 
            'message': '', 
            'data': {
                'agent_base_url': self.agent_base_url, 
                'start': True,
                'complete': False, 
                'returncode': None, 
                'out': None, 
                'err': None
            }
        }
        self._post_callback_url(callback_data)
         
        while True:
            try:
                if self.ps.poll() is None:
                    self.logger.debug('player process is running (%s)' % self.ps.pid)
                    self.process_dead = False 
                else:
                    self.logger.debug('player process is dead (exit %s)' % self.ps.returncode)
                    # -- realization of the fact here is potentially 3+ seconds late
                    self.process_dead = True 
                
                self.last_activity = datetime.now()
                
                self.read_loop = True 
                read_thread = threading.Thread(target=self.read_stream)
                read_thread.start()
                time.sleep(3)
                self.read_loop = False 
                read_thread.join()
                
                self.logger.debug(" - loop captured %s lines" % len(self.lines))
                
                if len(self.lines) > 0:
                    int_resp = {
                        'success': True, 
                        'message': '\n'.join(self.lines), 
                        'data': {
                            'agent_base_url': self.agent_base_url, 
                            'complete': False
                        }
                    }
                    self._post_callback_url(int_resp)
                else:
                    self.logger.debug("stdout is empty")
                
            except:
                self.logger.error(sys.exc_info()[0])
                self.logger.error(sys.exc_info()[1])
                traceback.print_tb(sys.exc_info()[2])
            finally:
               if self.process_dead and self.let_thread_die:
                   self.logger.debug("Exiting process monitor while loop (process_dead: %s, let_thread_die; %s)" % (self.process_dead, self.let_thread_die))
                   break
                   
        self.logger.debug("Waiting on player process..")
        returncode = self.ps.wait()
        (out, err) = self.ps.communicate(None)
        self.logger.debug("returncode: %s" % returncode)
        self.logger.debug("out: %s" % out)
        self.logger.debug("err: %s" % err)
        if self.report_complete:
            complete_data = {
                'success': True, 
                'message': '', 
                'data': {
                    'agent_base_url': self.agent_base_url, 
                    'complete': True, 
                    'returncode': returncode, 
                    'out': out, 
                    'err': err
                }
            }
            complete_response = self._post_callback_url(complete_data)
        else:
            self.logger.debug("Not calling complete response (callback_url: %s report_complete: %s)" % (self.callback_url, self.report_complete))
        
        self.logger.debug("Exiting monitor thread now")

    '''
    - start state: no thread, no process 
    - init state: no thread -> thread alive, process alive, no activity 
    - running state: thread alive, process alive, last activity 
    - spin down state: thread alive, process dead 
    - stop state: no thread, last activity 
    
    '''
    
    def expired_less_than(self, seconds_ago=0, logger=None):
        if not logger:
            logger = self.logger 
        expiration_age = (datetime.now() - self.last_activity).total_seconds() if self.last_activity else None        
        if expiration_age:
            logger.debug("Process monitor expired %s seconds ago" % expiration_age)
        else:
            logger.debug("Process monitor has no activity record")
        return expiration_age <= seconds_ago if expiration_age is not None else False 

    def is_alive(self, logger=None):
        if not logger:
            logger = self.logger 
        if self.monitor_thread:
            logger.debug(f'Process monitor thread: {self.monitor_thread.is_alive()}')
        else:
            logger.debug(f'Process monitor thread doesn\'t exist')
        return (self.monitor_thread and self.monitor_thread.is_alive())
    
    def process(self, ps, callback_url, agent_base_url):
        '''
        A thread can continue monitoring a process for output and completeness if the parameters are the same.
        Rather than the thread dying when it observes the process ending, it can honor a flag which cancels this response.
        When a new play 
        '''
        
        if self.is_alive():
            self.logger.debug("ProcessMonitor seems to be monitoring a process already.. waiting")
            self.monitor_thread.join()
            
        # self.logger.setLevel(level=logging._nameToLevel[log_level.upper()])
        self.lines = []
        self.process_dead = False 
        self.report_complete = True
        self.let_thread_die = True 
        
        self.ps = ps
        self.callback_url = callback_url 
        self.agent_base_url = agent_base_url
        
        if not self.is_alive():
            self.monitor_thread = threading.Thread(target=self.report_stream)
            self.monitor_thread.start()
        
        return True 
