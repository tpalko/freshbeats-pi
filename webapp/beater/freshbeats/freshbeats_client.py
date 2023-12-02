import sys
import os
from django.conf import settings
from django.http import JsonResponse
#from django.views.decorators.csrf import csrf_exempt
import logging
import traceback
import json
import threading
import time
import io
from beater.switchboard.switchboard import SwitchboardClient
from beater.common.util import get_session_value, set_session_value

sys.path.append(os.path.join(settings.BASE_DIR, "..", "services"))

from freshbeats import freshbeats, ingest

logger = logging.getLogger()

def _get_freshbeats(function_name, mobile_id):
    m = freshbeats.FreshBeats(mobile_id=mobile_id)
    return getattr(m, function_name)

def _get_ingest(function_name):
    m = freshbeats.Ingest()
    return getattr(m, function_name)
    
def apply_plan(request):
    success = False 
    mobile_id = get_session_value(request, 'mobile_id')
    if mobile_id:    
        success = _call_freshbeats(_get_freshbeats('apply_plan', mobile_id), add_randoms=False)
    return JsonResponse({'success': success})

def validate_plan(request):
    success = False 
    mobile_id = get_session_value(request, 'mobile_id')
    if mobile_id:
        success = _call_freshbeats(_get_freshbeats('validate_plan', mobile_id))
    return JsonResponse({'success': success})

def plan_report(request):
    success = False 
    mobile_id = get_session_value(request, 'mobile_id')
    if mobile_id:
        try:
            success = _call_freshbeats(_get_freshbeats('plan_report', mobile_id))
        except Exception as e:
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
            SwitchboardClient.getInstance().publish_event('device_output', json.dumps({'complete': True, 'out': str(e)}))
            
    return JsonResponse({'success': success})

def update_db(request):
    success = _call_freshbeats(_get_ingest('update_db'))
    return JsonResponse({'success': success})

def _call_freshbeats(function, *args, **kwargs):

    success = False 
    
    try:
        log_capture_string = io.StringIO()

        ch = logging.StreamHandler(log_capture_string)
        
        fb_logger = logging.getLogger('freshbeats.freshbeats')
        # -- this is the log level setting that actually determines the log level
        #fb_logger.setLevel(logging.INFO)
        fb_logger.addHandler(ch)

        t = threading.Thread(target=function, args=kwargs.values())
        t.start()

        while t.is_alive():
            logger.debug(f'publishing device_output for {function.__name__}')
            SwitchboardClient.getInstance().publish_event('device_output', json.dumps({'function_name': function.__name__, 'complete': False, 'out': log_capture_string.getvalue()}))
            time.sleep(1)
        
        logger.debug(f'publishing device_output for {function.__name__}')
        SwitchboardClient.getInstance().publish_event('device_output', json.dumps({'function_name': function.__name__, 'complete': True, 'out': log_capture_string.getvalue()}))
        
        t.join()
        fb_logger.removeHandler(ch)
        success = True 
        
    except:
        logger.error(sys.exc_info()[0])
        logger.error(sys.exc_info()[1])
        traceback.print_tb(sys.exc_info()[2])
    finally:
        log_capture_string.close()

    return success 
