from django.conf import settings
import requests


def _publish_event(event, payload):
    '''Send a message through switchboard'''
    # logger.debug("publishing %s: %s" % (event, payload))
    headers = {"content-type": "application/json"}
    requests.post('http://%s:%s/pushevent/%s' % (
        settings.SWITCHBOARD_SERVER_HOST,
        settings.SWITCHBOARD_SERVER_PORT,
        event), headers=headers, data=payload)
