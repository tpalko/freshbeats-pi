import logging
import requests
import time 
import sys 
import os 

logger = logging.getLogger()

class SwitchboardClient(object):

    host = None 
    port = None 
    headers = None 
    client_url_base = None 

    __instance = None 

    @staticmethod
    def getInstance(host=None, port=None):

        # 
        if not SwitchboardClient.__instance:
            SwitchboardClient(host=host, port=port)

        return SwitchboardClient.__instance 

    def __init__(self, *args, **kwargs):

        if not SwitchboardClient.__instance:

            logger.debug(f'No switchboard client instance.. making a new one')

            for k in kwargs:
                self.__setattr__(k, kwargs[k])

            if not self.host:
                self.host = os.getenv('FRESHBEATS_SWITCHBOARD_HOST_BEATER_APP')
            
            if not self.port:
                self.port = os.getenv('FRESHBEATS_SWITCHBOARD_PORT_BEATER_APP')

            if not self.host or not self.port:
                logger.error(f'SwitchboardClient requires host and port. (Provided: host={self.host}, port={self.port})')
                raise Exception(f'SwitchboardClient requires host and port. (Provided: host={self.host}, port={self.port})')
            
            if not self.headers:
                self.headers = {"content-type": "application/json"}

            if not self.client_url_base:
                self.client_url_base = f'http://{self.host}:{self.port}/pushevent/'

            SwitchboardClient.__instance = self 
        
        if not SwitchboardClient.__instance:
            logger.error(f'Still no switchboard client.. fail')
        else:
            logger.debug(f'Switchboard client  yay')
    
    def _push(self, event, payload, connection_id=None):
        # j = json.loads(data)
        # if 'complete' in j:
        #     defLogger.info("_publish_event called (complete %s).." % j['complete'])
        
        response = None 
        sent = False 
        attempts = 0
        connection_id_path = f'/{connection_id}' if connection_id else ''
        
        while not sent and attempts < 10:
            try:            
                attempts += 1
                #logger.info("Posting (%s).." % client_url)
                response = requests.post(f'{self.client_url_base}/{event}{connection_id_path}', headers=self.headers, data=payload)
                #logger.info("Posted (%s)" % response)
                if response.ok:
                    #logger.info("Response ok")
                    sent = True 
                    break 
            except:
                logger.warn("Post to switchboard failed")
                logger.warn(str(sys.exc_info()[1]))

            if response:
                logger.warn("Not okay switchboard response:")
                logger.warn(response.content)
            time.sleep(3)
            response = None 

    def publish_event(self, event, payload="{}", connection_id=None):
        # -- payload = {"function_name": "", "complete": "", "out": ""}
        '''Send a message through switchboard'''
        #logger.info("Loading..")
        
        #logger.info("Loaded")
        
        #logger.info("publishing %s: payload length %s" % (event, len(payload)))
        self._push(event=event, payload=payload, connection_id=connection_id)
        
        
