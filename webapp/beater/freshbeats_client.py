import sys
import os
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import logging
import traceback
import json
import threading
import time
import io
from .switchboard import _publish_event

sys.path.append(os.path.join(settings.BASE_DIR, "..", "services"))
from freshbeats import freshbeats, ingest

def _get_freshbeats(function_name):
    m = freshbeats.FreshBeats()
    return getattr(m, function_name)

def _get_ingest(function_name):
    m = freshbeats.Ingest()
    return getattr(m, function_name)
    
@csrf_exempt
def apply_plan(request):

    _call_freshbeats(_get_freshbeats('apply_plan'), add_randoms=False)
    return JsonResponse({'success': True})

@csrf_exempt
def validate_plan(request):

    _call_freshbeats(_get_freshbeats('validate_plan'))
    return JsonResponse({'success': True})

@csrf_exempt
def plan_report(request):

    _call_freshbeats(_get_freshbeats('plan_report'))
    return JsonResponse({'success': True})

@csrf_exempt
def update_db(request):

    _call_freshbeats(_get_ingest('update_db'))
    return JsonResponse({'success': True})

def _call_freshbeats(function, *args, **kwargs):

    try:
        log_capture_string = io.StringIO()

        ch = logging.StreamHandler(log_capture_string)

        logger = logging.getLogger('FreshBeats')
        # -- this is the log level setting that actually determines the log level
        logger.setLevel(logging.INFO)
        logger.addHandler(ch)

        t = threading.Thread(target=function, args=kwargs.values())
        t.start()

        while t.isAlive():
            _publish_event('device_output', json.dumps({'function_name': function.__name__, 'complete': False, 'out': log_capture_string.getvalue()}))
            time.sleep(1)

        _publish_event('device_output', json.dumps({'function_name': function.__name__, 'complete': True, 'out': log_capture_string.getvalue()}))

        logger.removeHandler(ch)

    except:
        logger.error(sys.exc_info()[1])
        traceback.print_tb(sys.exc_info()[2])
    finally:
        log_capture_string.close()

    return True
