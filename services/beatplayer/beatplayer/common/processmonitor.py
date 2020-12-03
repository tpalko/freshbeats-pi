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
    
    play_thread = None 
    expired_at = None 
    
    def run_in_thread(ps, callback_url):#, command, force):
        '''Thread target'''
        logger.info("Waiting for self.ps..")                
        
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
                if ps.poll() is not None:
                    logger.debug('player process is dead')
                    process_dead = True 
                    ProcessMonitor.expired_at = datetime.now()
                else:
                    logger.debug('player process is running (%s)' % ps.pid)
                
                logger.debug("reading from player stdout..")
                lines = []
                next_line = ps.stdout.readline()
                while next_line != '' and 'Broken pipe' not in next_line:
                    logger.debug(next_line)
                    lines.append(next_line)
                    time.sleep(0.3)
                    # logger.debug(dir(ps))
                    # logger.debug(dir(ps.stdout))
                    next_line = ps.stdout.readline()
                    logger.debug("line was read..")
                logger.debug("done reading")
                int_resp['message'] = '\n'.join(lines)
                
                if len(int_resp['message']) > 0:
                    logger.debug('intermittent response has a message: %s' % int_resp["message"])
                    for line in lines:
                        logger.debug("STDOUT: %s" % line)
                    if callback_url:
                        requests.post(callback_url, headers={'content-type': 'application/json'}, data=json.dumps(int_resp))
                else:
                    logger.debug("stdout is empty")
                
                if len(int_resp['message']) > 0:
                    int_resp['message'] = ''
                else:
                    time.sleep(1)
            except:
                logger.error(sys.exc_info()[0])
                logger.error(sys.exc_info()[1])
                traceback.print_tb(sys.exc_info()[2])
            finally:
               if process_dead:
                   logger.debug("process is dead, exiting stdout while loop")
                   break
                   
        logger.debug("Waiting on player process..")
        returncode = ps.wait()
        (out, err) = ps.communicate(None)
        logger.debug("returncode: %s" % returncode)
        logger.debug("out: %s" % out)
        logger.debug("err: %s" % err)
        if callback_url:
            callback_response = {'success': True, 'message': '', 'data': {'complete': True, 'returncode': returncode, 'out': out, 'err': err}}
            requests.post(callback_url, headers={'content-type': 'application/json'}, data=json.dumps(callback_response))
        return

    @staticmethod 
    def is_alive():
        return (ProcessMonitor.play_thread and ProcessMonitor.play_thread.is_alive()) or (ProcessMonitor.expired_at is not None and (datetime.now() - ProcessMonitor.expired_at).total_seconds() < 5)

    @staticmethod 
    def process(ps, callback_url, log_level='INFO'):
        logger.setLevel(level=logging._nameToLevel[log_level.upper()])
        ProcessMonitor.expired_at = None 
        ProcessMonitor.play_thread = threading.Thread(target=ProcessMonitor.run_in_thread, args=(ps, callback_url,)) #, command, force))
        ProcessMonitor.play_thread.start()
        return ProcessMonitor.play_thread
