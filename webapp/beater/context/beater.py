from django.conf import settings

socketio_host = settings.SWITCHBOARD_SERVER_HOST
socketio_port = settings.SWITCHBOARD_SERVER_PORT

def switchboard_processor(request_context):
	return { 'socketio_host': socketio_host, 'socketio_port': socketio_port }