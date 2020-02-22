from django.conf import settings
import logging
import requests
import json
import time 
import sys 

logger = logging.getLogger('FreshBeats')
defLogger = logging.getLogger()

def _publish_event(event, payload):
    # -- payload = {"function_name": "", "complete": "", "out": ""}
    '''Send a message through switchboard'''
    j = json.loads(payload)
    if 'complete' in j:
        defLogger.info("_publish_event called (complete %s).." % j['complete'])
    logger.debug("publishing %s: %s" % (event, payload))
    headers = {"content-type": "application/json"}
    response = None 
    sent = False 
    attempts = 0
    while not sent and attempts < 10:
        try:            
            attempts += 1
            response = requests.post('http://%s:%s/pushevent/%s' % (
                settings.SWITCHBOARD_SERVER_HOST_BEATER_APP,
                settings.SWITCHBOARD_SERVER_PORT_BEATER_APP,
                event), headers=headers, data=payload)
            if response.ok:
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
