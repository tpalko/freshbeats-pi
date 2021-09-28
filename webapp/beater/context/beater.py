import logging

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import resolve 

from ..models import Device, DeviceHealth

logger = logging.getLogger(__name__)

def switchboard_processor(request_context):
    '''Dynamically determine conventionally named js include file'''

    page_script_path = None

    try:
        # -- /beater/hello becomes js/hello.js
        # -- /beater/what/is/my/js becomes js/what/is/my/js.js
        current_path_tokens = [ p for p in request_context.path.split('/') if p and p != settings.SITE_BASE_URL ]
        if len(current_path_tokens) > 0:
            page_script_path = "js/%s.js" % ('/'.join(current_path_tokens))
            # -- this allows server-side scripting in javascript includes 
            render_to_string(page_script_path)        
    except Exception as e:
        logger.warn("page js at '%s' does not exist", page_script_path)
        page_script_path = None
    
    menu = [
        { 'url': 'search', 'display': 'search' },
        { 'url': 'devices', 'display': 'devices' },
        { 'url': 'mobile', 'display': 'mobile' },
        { 'url': 'manage', 'display': 'collection' },
        { 'url': 'report', 'display': 'report' },
        { 'url': 'playlists', 'display': 'playlists' },
        { 'url': 'survey', 'display': 'survey' }
    ]
    
    selected_device_id = None 
    if 'device_id' in request_context.session:
        selected_device_id = request_context.session['device_id']
        logger.debug("device_id found on session: %s" % selected_device_id)
    else:
        other_ready_devices = Device.objects.filter(Q(health__status=DeviceHealth.DEVICE_STATUS_READY))
        if len(other_ready_devices) > 0:
            selected_device_id = other_ready_devices[0].id
        logger.debug("device_id NOT found on session")

    return {
        'socketio_host': settings.SWITCHBOARD_SERVER_HOST_BROWSER,
        'socketio_port': settings.SWITCHBOARD_SERVER_PORT_BROWSER,
        'page_script_path': page_script_path,
        'url_name': resolve(request_context.path_info).url_name,
        'devices': Device.objects.all(),
        'selected_device_id': selected_device_id,
        'menu': menu
    }
