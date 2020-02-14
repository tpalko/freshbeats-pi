from django.conf import settings
import logging
import requests
import json

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
    response = requests.post('http://%s:%s/pushevent/%s' % (
        settings.SWITCHBOARD_SERVER_INTERNAL_HOST,
        settings.SWITCHBOARD_SERVER_INTERNAL_PORT,
        event), headers=headers, data=payload)
    logger.debug(response)
