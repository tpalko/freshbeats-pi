import base64
import logging
import requests
import json
import time 
import sys 
from contextlib import contextmanager 
from django.conf import settings
from django.contrib.sessions.models import Session
from datetime import datetime 
from pytz import timezone 

UTC = timezone('UTC')
logger = logging.getLogger(__name__)
# defLogger = logging.getLogger()

def session_data():
    all_sessions = Session.objects.all()
    now = UTC.localize(datetime.utcnow())
    for session in [ s for s in all_sessions if s.expire_date > now]:
        decoded = base64.decodestring(session.session_data.encode()).decode('utf-8').partition(':')
        session_data = json.loads(decoded[2])
        yield session_data 

def _get_playlist_id_for_switchboard_connection_id(connection_id):
    playlist_id = None 
    for data in session_data():
        if 'switchboard_connection_id' in data and data['switchboard_connection_id'] == connection_id:
            playlist_id = data['playlist_id'] if 'playlist_id' in data else None 
            if playlist_id is not None:
                break 
    return playlist_id

def _get_switchboard_connection_id_for_device_id():
    device_switchboard_connection_ids = {}
    for data in session_data():
        if 'device_id' in data:
            device_id = int(data['device_id'])
            if device_id in device_switchboard_connection_ids:
                device_switchboard_connection_ids[device_id].append(data['switchboard_connection_id'])
            else:
                device_switchboard_connection_ids[device_id] = [data['switchboard_connection_id']]
    return device_switchboard_connection_ids
    
def _push(event, payload, connection_id=None):
    # j = json.loads(data)
    # if 'complete' in j:
    #     defLogger.info("_publish_event called (complete %s).." % j['complete'])
    headers = {"content-type": "application/json"}
    response = None 
    sent = False 
    attempts = 0
    connection_id_path = ""
    if connection_id:
        connection_id_path = "/%s" % connection_id
    client_url = 'http://%s:%s/pushevent/%s%s' % (settings.SWITCHBOARD_SERVER_HOST_BEATER_APP, settings.SWITCHBOARD_SERVER_PORT_BEATER_APP, event, connection_id_path)
    while not sent and attempts < 10:
        try:            
            attempts += 1
            #logger.info("Posting (%s).." % client_url)
            response = requests.post(client_url, headers=headers, data=payload)
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

def _publish_event(event, payload="{}", connection_id=None):
    # -- payload = {"function_name": "", "complete": "", "out": ""}
    '''Send a message through switchboard'''
    #logger.info("Loading..")
    
    #logger.info("Loaded")
    
    #logger.info("publishing %s: payload length %s" % (event, len(payload)))
    _push(event=event, payload=payload, connection_id=connection_id)
    
    
