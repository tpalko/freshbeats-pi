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
from cStringIO import StringIO
from .switchboard import _publish_event

sys.path.append(os.path.join(settings.BASE_DIR, "..", "services"))
from freshbeats import freshbeats


def apply_plan(request):

    _call_freshbeats('apply_plan', add_randoms=False)
    return JsonResponse({'success': True})


def validate_plan(request):

    _call_freshbeats('validate_plan')
    return JsonResponse({'success': True})


def plan_report(request):

    _call_freshbeats('plan_report')
    return JsonResponse({'success': True})


def update_db(request):

    _call_freshbeats('update_db')
    return JsonResponse({'success': True})


def _call_freshbeats(function_name, *args, **kwargs):

    try:
        log_capture_string = StringIO()

        ch = logging.StreamHandler(log_capture_string)

        logger = logging.getLogger('FreshBeats')
        logger.addHandler(ch)

        f = freshbeats.FreshBeats()
        fresh_function = getattr(f, function_name)

        t = threading.Thread(target=fresh_function, args=kwargs.values())
        t.start()

        while t.isAlive():
            _publish_event('device_output', json.dumps({'function_name': function_name, 'complete': False, 'out': log_capture_string.getvalue()}))
            time.sleep(1)

        _publish_event('device_output', json.dumps({'function_name': function_name, 'complete': True, 'out': log_capture_string.getvalue()}))

    except:
        logger.error(sys.exc_info()[1])
        traceback.print_tb(sys.exc_info()[2])
    finally:
        log_capture_string.close()

    return True
