import logging 
import time 
import json 
import requests 
import threading 
import traceback 
from datetime import datetime 

logging.basicConfig(
    level=logging.WARN,
    format='[ %(levelname)7s ] %(asctime)s %(name)-17s %(filename)s:%(lineno)-4d %(message)s'
)
#f_handler = logging.FileHandler(filename='processmonitor.log', mode='a')
logger = logging.getLogger(__name__)
#logger.addHandler(f_handler)

class ProcessMonitor():
    
    __instance = None 
    
    monitor_thread = None     
    last_activity = None 
    process_dead = True
    lines = None 
    report_complete = True
    
    @staticmethod
    def getInstance():
        if ProcessMonitor.__instance is None:
            ProcessMonitor()
        return ProcessMonitor.__instance
    
    def __init__(self, *args, **kwargs):
        if ProcessMonitor.__instance is not None:
            raise Exception("Call ProcessMonitor.getInstance()")
        ProcessMonitor.__instance = self
    
    def read_stream(self, ps):
        while self.read_loop:
            self.lines.append(ps.stdout.readline())
            time.sleep(0.3)
        
    def report_stream(self, ps, callback_url, agent_base_url):#, command, force):
        '''Thread target'''
        logger.info("Waiting for self.ps..")                
        
        int_resp = {'success': True, 'message': '', 'data': {'agent_base_url': agent_base_url, 'complete': False}} 
        '''
        order matters:
            read - post - break (don't lose data)
            check - read - break (break on what we knew before the read)
            start - break - sleep (so we don't sleep unnecessarily)
        '''
        
        initial_callback_data = {
            'agent_base_url': agent_base_url, 
            'start': True,
            'complete': False, 
            'returncode': None, 
            'out': None, 
            'err': None
        }
        callback_response = {'success': True, 'message': '', 'data': initial_callback_data}
        requests.post(callback_url, headers={'content-type': 'application/json'}, data=json.dumps(callback_response))
        
        while True:
            try:
                if ps.poll() is None:
                    logger.debug('player process is running (%s)' % ps.pid)
                else:
                    logger.debug('player process is dead (exit %s)' % ps.returncode)
                    # -- realization of the fact here is potentially 3+ seconds late
                    self.process_dead = True 
                
                self.last_activity = datetime.now()
                
                self.read_loop = True 
                read_thread = threading.Thread(target=self.read_stream, args=(ps,))
                read_thread.start()
                time.sleep(3)
                self.read_loop = False 
                read_thread.join()
                
                logger.debug(" - loop captured %s lines" % len(self.lines))
                    
                int_resp['message'] = '\n'.join(self.lines)
                
                if len(int_resp['message']) > 0:
                    logger.debug('intermittent response has a message: %s' % int_resp["message"])
                    if callback_url:
                        requests.post(callback_url, headers={'content-type': 'application/json'}, data=json.dumps(int_resp))
                else:
                    logger.debug("stdout is empty")
                
                int_resp['message'] = ''
                
            except:
                logger.error(sys.exc_info()[0])
                logger.error(sys.exc_info()[1])
                traceback.print_tb(sys.exc_info()[2])
            finally:
               if self.process_dead:
                   logger.debug("process is dead, exiting stdout while loop")
                   break
                   
        logger.debug("Waiting on player process..")
        returncode = ps.wait()
        (out, err) = ps.communicate(None)
        logger.debug("returncode: %s" % returncode)
        logger.debug("out: %s" % out)
        logger.debug("err: %s" % err)
        if callback_url and self.report_complete:
            callback_response = {'success': True, 'message': '', 'data': {'agent_base_url': agent_base_url, 'complete': True, 'returncode': returncode, 'out': out, 'err': err}}
            requests.post(callback_url, headers={'content-type': 'application/json'}, data=json.dumps(callback_response))

    '''
    - start state: no thread, no process 
    - init state: no thread -> thread alive, process alive, no activity 
    - running state: thread alive, process alive, last activity 
    - spin down state: thread alive, process dead 
    - stop state: no thread, last activity 
    
    '''
    
    def expired_less_than(self, seconds_ago=0):
        return (datetime.now() - self.last_activity).total_seconds() <= seconds_ago if self.last_activity is not None else False 
        
    def is_alive(self):
        return (self.monitor_thread and self.monitor_thread.is_alive())

    def process(self, ps, callback_url, agent_base_url, log_level='INFO'):
        
        if self.is_alive():
            logger.debug("ProcessMonitor seems to be monitoring a process already.. waiting")
            self.monitor_thread.join()
            
        logger.setLevel(level=logging._nameToLevel[log_level.upper()])
        self.process_dead = False 
        self.lines = []
        self.report_complete = True
        self.monitor_thread = threading.Thread(target=self.report_stream, args=(ps, callback_url, agent_base_url,)) #, command, force))
        self.monitor_thread.start()
        
        return True 
