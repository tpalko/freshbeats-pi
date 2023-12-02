import sys 
import os 
from gunicorn.app import wsgiapp 

from services.beatplayer.server.serving import handler 

app = wsgiapp.WSGIApplication(handler)
app.run()