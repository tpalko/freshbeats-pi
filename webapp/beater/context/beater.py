import os
from django.conf import settings
from django.template.loader import render_to_string
import logging

socketio_host = settings.SWITCHBOARD_SERVER_HOST
socketio_port = settings.SWITCHBOARD_SERVER_PORT

logger = logging.getLogger(__name__)
fresh_logger = logging.StreamHandler()

logger.setLevel(logging.DEBUG)
logger.addHandler(fresh_logger)

def switchboard_processor(request_context):

	page_script_path = None

	try:
		page_script_path = "js/%s.js" %('/'.join([ p for p in request_context.path.split('/') if p ]))
		render_to_string(page_script_path)
	except:
		logger.error("page js at '%s' does not exist" % page_script_path)
		page_script_path = None

	return { 
		'socketio_host': socketio_host, 
		'socketio_port': socketio_port,
		'page_script_path': page_script_path
	}