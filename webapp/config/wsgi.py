"""
WSGI config for beater project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
"""

import os
#import site 

#site.addsitedir('/home/debian/tpalko/.virtualenv/freshbeats/local/lib/python2.7/site-packages')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_env")

#activate_env=os.path.expanduser("/home/debian/tpalko/.virtualenv/freshbeats/bin/activate_this.py")
#execfile(activate_env, dict(__file__=activate_env))

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
