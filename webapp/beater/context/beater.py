from django.conf import settings
from django.template.loader import render_to_string
import logging

LOGGER = logging.getLogger(__name__)
# fresh_logger = logging.StreamHandler()

LOGGER.setLevel(logging.DEBUG)
# logger.addHandler(fresh_logger)


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
        LOGGER.warn("page js at '%s' does not exist", page_script_path)
        page_script_path = None

    return {
        'socketio_host': settings.SWITCHBOARD_SERVER_HOST_BROWSER,
        'socketio_port': settings.SWITCHBOARD_SERVER_PORT_BROWSER,
        'page_script_path': page_script_path
    }
