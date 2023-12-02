from django.contrib.sessions.models import Session
from datetime import datetime 
from pytz import timezone 

UTC = timezone('UTC')

def _switchboard_connection_session_data():
    '''Generator for current, decoded session data with switchboard_connection_id'''

    all_sessions = Session.objects.all()
    now = UTC.localize(datetime.utcnow())
    for get_decoded_data in [ s.get_decoded() for s in all_sessions if s.expire_date > now and 'switchboard_connection_id' in s.get_decoded() ]:      
        # data_to_pad = session.session_data 
        # while len(data_to_pad) % 4 != 0:
        #     logger.debug(f'b64 session data: {session.session_data} mod 4 {len(data_to_pad) % 4}')
        #     data_to_pad += "="
        # session_data_bytes = data_to_pad.encode()
        # logger.debug(f'b64 session data bytes: {session_data_bytes} mod 4 {len(session_data_bytes) % 4}')
        # decoded_session_data = base64.decodebytes(session_data_bytes)
        # logger.debug(f'decoded session data: {decoded_session_data}')
        # decoded = decoded_session_data.decode('utf-8').partition(':')
        # session_data = json.loads(decoded[2])
        yield get_decoded_data

def get_playlist_id_for_switchboard_connection_id(connection_id):
    playlist_id = None 
    for data in _switchboard_connection_session_data():
        if data['switchboard_connection_id'] == connection_id:
            playlist_id = data['playlist_id'] if 'playlist_id' in data else None 
            if playlist_id is not None:
                break 
    return playlist_id

def get_switchboard_connection_id_for_device_id():
    '''Returns a map of switchboard connection IDs by device ID'''

    device_switchboard_connection_ids = {}
    for data in _switchboard_connection_session_data():
        if 'device_id' in data:
            device_id = int(data['device_id'])
            if device_id in device_switchboard_connection_ids:
                device_switchboard_connection_ids[device_id].append(data['switchboard_connection_id'])
            else:
                device_switchboard_connection_ids[device_id] = [data['switchboard_connection_id']]
    return device_switchboard_connection_ids