import unittest
import sys
import os
from collections import namedtuple

sys.path.append("../")

from freshbeats import FreshBeats

sys.path.append('../../../webapp')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_dev")

from beater.models import Album

class TestFreshbeatsDeviceOperations(unittest.TestCase):

	_freshbeats = None

	def setUp(self):

		try:
			os.mkdir('./testtarget')
		except OSError:
			pass

		options = namedtuple('options', ['mark_albums', 'copy_files', 'update_db'])
		options.mark_albums = False
		options.copy_files = False
		options.update_db = False

		args = [os.path.join(os.path.dirname(__file__), 'testtarget')]

		self._freshbeats = FreshBeats(options, args)

	def tearDown(self):

		os.rmdir('./testtarget')

	def test_get_space(self):

		space = self._freshbeats._get_space()

		self.failIf(not space)

	def test_copy_album_to_device(self):

		a = Album.objects.all()[0]

		self._freshbeats._copy_album_to_device(a)

def main():
	unittest.main()

if __name__ == "__main__":
	main()


