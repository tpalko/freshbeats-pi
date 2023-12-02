import logging
import os 
import sys 
import requests 
import json

import django
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../webapp'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'
django.setup()

logger = logging.getLogger()

class BeatplayerClient():

    url = None 
    headers = None 

    def __init__(self, *args, **kwargs):
        self.url = args[0]
        self.headers = {'content-type': 'application/json'}

    def _call(self, method, path, data={}):
        response = requests.request(method, f'{self.url}{path}', data=json.dumps(data), headers=self.headers)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as he:
            logger.error(f'error calling {method} {path}')
            logger.error(he)
        else:
            return response.json()

    def echo(self):
        return self._call('GET', '/echo')

    def healthz(self):
        return self._call('GET', '/healthz')

    def register_client(self, callback_url, agent_base_url):
        data = {
            'callback_url': callback_url,
            'agent_base_url': agent_base_url
        }
        return self._call('POST', '/register_client', data=data)

    def play(self, url, filepath, callback_url, agent_base_url):
        data = {
            'url': url,
            'filepath': filepath,
            'callback_url': callback_url,
            'agent_base_url': agent_base_url
        }
        return self._call('POST', '/play', data=data)

    def stop(self):
        return self._call('POST', '/stop')

    def mute(self):
        return self._call('POST', '/mute')

    def pause(self):
        return self._call('POST', '/pause')

    def volume_down(self):
        return self._call('POST', '/volume_down')

    def volume_up(self):
        return self._call('POST', '/volume_up')
