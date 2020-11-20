import logging

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import resolve 

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
        { 'url': 'mobile', 'display': 'devices' },
        { 'url': 'manage', 'display': 'collection' },
        { 'url': 'report', 'display': 'report' },
        { 'url': 'playlists', 'display': 'playlists' },
        { 'url': 'survey', 'display': 'survey' }
    ]

    return {
        'socketio_host': settings.SWITCHBOARD_SERVER_HOST_BROWSER,
        'socketio_port': settings.SWITCHBOARD_SERVER_PORT_BROWSER,
        'page_script_path': page_script_path,
        'url_name': resolve(request_context.path_info).url_name,
        'menu': menu
    }
