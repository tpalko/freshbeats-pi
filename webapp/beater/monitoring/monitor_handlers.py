import json
import sys
import traceback

import logging
from beater.monitoring.health import BeatplayerHealth
from beater.beatplayer.player import PlayerWrapper
from beater.switchboard.switchboard import SwitchboardClient
from beater.models import Device
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger()
health_logger = logging.getLogger('beater.beatplayer.health')
health_reg_logger = logging.getLogger('beater.beatplayer.health.reg')

@require_http_methods(['POST'])
def register_client(request):    
    user_agent = request.POST.get('userAgent')
    connection_id = request.POST.get('connectionId')
    request.session['switchboard_connection_id'] = connection_id
    request.session['user_agent'] = user_agent 
    # session_key = request.session.session_key
    return JsonResponse({'success': True})

# @csrf_exempt
# @require_http_methods(['POST'])
# def device_health_loop(request):
#     response = {'success': False, 'message': ''}
#     try:
#         body = json.loads(request.body.decode())
#         agent_base_url = body['agent_base_url'] # request.POST.get('agent_base_url')
#         if agent_base_url:
#             beatplayer = BeatplayerHealth.getInstance(agent_base_url)
#             beatplayer.check_if_health_loop()
#             response['success'] = True
#         else:
#             response['message'] = "agent_base_url is %s" % agent_base_url
#     except:
#         response['message'] = str(sys.exc_info()[1])
#     return JsonResponse(response)

@csrf_exempt
def device_health_report(request):
    '''Endpoint for beatplayer health pings'''

    response = {'message': "", 'success': False, 'result': {}}
    try:
        health = json.loads(request.body.decode())
        
        if not health['success'] and health['message'] and len(health['message']) > 0:
            SwitchboardClient.getInstance().publish_event('message', json.dumps(health['message']))
        
        health_logger.debug("health response: %s" % json.dumps(health, indent=4))
        health_data = health['data']
        
        #health_logger.debug('Health response: %s' % (json.dumps(health_data, indent=4)))
        agent_base_url = health_data['agent_base_url']
        
        health_logger.debug("Parsing health response in BeatplayerRegistrar..")
        beatplayer = BeatplayerHealth.getInstance(agent_base_url=agent_base_url)
        beatplayer.log_device_health_report(health_data)
        
        with beatplayer.device(read_only=True) as device:
            health_logger.debug("Parsing health response in PlayerWrapper..")
            playlist_id = request.session['playlist_id'] if 'playlist_id' in request.session else None 
            player = PlayerWrapper.getInstance(device_id=device.id)
            player_args = {
                'playlist_id': playlist_id, 
                'health_data': health_data,
                'logger': health_logger
            }
            player.call('parse_state', **player_args)
        
        response['success'] = True 
    except Exception as e:
        response['message'] = str(sys.exc_info()[1])
        health_logger.error(sys.exc_info()[0])
        health_logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        # health_logger.error(dir(sys.exc_info()[2]))
        # health_logger.error(sys.exc_info()[2].tb_frame.f_code)
        # health_logger.error(sys.exc_info()[2].tb_frame.f_lineno)
        # health_logger.error(sys.exc_info()[2].tb_frame.f_locals)
        SwitchboardClient.getInstance().publish_event('alert', json.dumps({'message': response['message']}))
    
    health_logger.debug("Finished processing health response")
    return JsonResponse(response)

def log_client_presence(request):
    if 'caller' in request.POST:
        health_reg_logger.info(f'Client presence call from {request.POST["caller"]}')
    else:
        health_reg_logger.warning(f'Client presence call from unknown')
    success = False 
    if 'device_id' not in request.session:
        health_reg_logger.warn('No device ID on request.session, cannot log client presence')
    else:
        device = Device.objects.get(pk=request.session['device_id'])
        beatplayer = BeatplayerHealth.getInstance(device.agent_base_url)
        beatplayer.log_client_presence()
        success = True
    return JsonResponse({'success': success})

def player_status_and_state(request):

    response = {'result': {}, 'success': False, 'message': ""}

    try:
        if 'device_id' not in request.session:
            raise Exception('device_id not found in session when attempting to trigger player show_player_status')
            
        device = Device.objects.get(pk=request.session['device_id'])            
        #playlist_id = request.session['playlist_id'] if 'playlist_id' in request.session else None 
        player = PlayerWrapper.getInstance(device_id=device.id)
        player.show_player_status()
        response['success'] = True
    except:
        response['message'] = str(sys.exc_info()[1])
        logger.error(response['message'])
        traceback.print_tb(sys.exc_info()[2])
        SwitchboardClient.getInstance().publish_event('message', json.dumps(response['message']))

    return JsonResponse({'success': True})