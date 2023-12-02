import cowpy
import sys 
from jroutes.routing import responsify, authorize, route, context
from beatplayer.health import PlayerHealth
from beatplayer.basewrapper import BaseWrapper 
import threading

# from webapp.beater.models import Player 
logger = cowpy.getLogger()
health_logger = cowpy.getLogger(name='beatplayer.health')
action_logger = cowpy.getLogger(name='beatplayer.action')

# -- TODO: for when we implement context support in jroutes 
# @context()
# def _init(context, next):
#     context['player'] = BaseWrapper.getInstance()
#     context['health'] = PlayerHealth.getInstance()
#     next(context)

@route("/healthz", "GET")
def healthz(body, query):
    
    # -- context work
    # player = jtext.context['player']
    # healthz_response = jtext.context['health'].healthz(player)
    
    player = BaseWrapper.getInstance(logger=health_logger)
    health = PlayerHealth.getInstance()
    healthz_response = health.healthz(player)

    health_logger.debug('healthz_response:')
    health_logger.debug(healthz_response)
    return healthz_response
    
@route('/play', "POST")
def play(body, query):

    # body = jtext.body
    # player = jtext.context['player']

    action_logger.debug(body)

    # health = PlayerHealth.getInstance()
    player = BaseWrapper.getInstance(logger=action_logger)

    url = body['url']
    filepath = body['filepath']
    callback_url = body['callback_url']
    agent_base_url = body['agent_base_url']
    
    command_thread = threading.Thread(target=player.issue_command, args=(url, filepath, callback_url, agent_base_url,))
    command_thread.start()
    what = command_thread.join()
    
    return {'success': True, 'message': '', 'data': {}}

@route('/register_client', "POST")
def register_client(body, query):
    # body = jtext.body
    # health = jtext.context['health']
    # player = jtext.context['player'
    
    returnObj = {'success': False, 'message': '', 'data': {}}

    try:
        # callback_url, agent_base_url
        callback_url = body['callback_url']
        agent_base_url = body['agent_base_url']
        health = PlayerHealth.getInstance()
        player = BaseWrapper.getInstance(logger=health_logger)

        returnObj['data'] = health.register_client(callback_url, agent_base_url, player)
        returnObj['success'] = True 
    except:        
        returnObj['message'] = str(sys.exc_info()[1])
        health_logger.exception()
        # logger.error(returnObj['message'])

    return returnObj 

@route('/stop', "POST")
def stop(body, query):
    player = BaseWrapper.getInstance(logger=action_logger)
    player.stop()
    return {'success': True, 'message': '', 'data': {}}

@route('/mute', "POST")
def mute(body, query):
    return {'success': True, 'message': '', 'data': {}}

@route('/pause', "POST")
def pause(body, query):
    return {'success': True, 'message': '', 'data': {}}

@route('/volume_down', "POST")
def volume_down(body, query):
    return {'success': True, 'message': '', 'data': {}}

@route('/volume_up', "POST")
def volume_up(body, query):
    return {'success': True, 'message': '', 'data': {}}
