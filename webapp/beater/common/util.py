from django.http import HttpResponse, JsonResponse
from datetime import datetime 
from pytz import timezone 

UTC = timezone("UTC")

def get_session_value(request, key, default=None):
    if key in request.session:
        return request.session[key]
    return default  

def set_session_value(request, key, value, force=False):
    if force or key not in request.session:
        request.session[key] = value

def get_localized_now():
    return timezone("UTC").localize(datetime.now())
    
def capture(f):
	"""
	Decorator to capture standard output
	"""
	def captured(*args, **kwargs):
		import sys
		from cStringIO import StringIO

		# setup the environment
		backup_out = sys.stdout
		backup_err = sys.stderr

		out = ""
		err = ""
		
		try:
			sys.stdout = StringIO()     # capture output
			sys.stderr = StringIO()
			f(*args, **kwargs)
			out = sys.stdout.getvalue() # release output
			err = sys.stderr.getvalue()
		finally:
			sys.stdout.close()  # close the stream 
			sys.stderr.close()
			sys.stdout = backup_out # restore original stdout
			sys.stderr = backup_err

		return JsonResponse({'out': out, 'err': err}) # captured output wrapped in a string

	return captured

'''
import contextlib
@contextlib.contextmanager
def capture():
	import sys
	from cStringIO import StringIO
	oldout,olderr = sys.stdout, sys.stderr
	try:
		out=[StringIO(), StringIO()]
		sys.stdout,sys.stderr = out
		yield out
	finally:
		sys.stdout,sys.stderr = oldout, olderr
		out[0] = out[0].getvalue()
		out[1] = out[1].getvalue()
'''
