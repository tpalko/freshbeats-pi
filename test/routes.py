import sys 
import os 

sys.path.append(os.path.join(os.path.dirname(__name__), 'services', 'beatplayer'))

from server.routing import authorize, route, JsonResponse
    
@route('/testthing', 'POST')
def testthing(body, query):
    return {'success': True, 'message': '', 'data': {}}
