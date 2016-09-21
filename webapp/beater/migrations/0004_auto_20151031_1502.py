# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def forwards_func(apps, schema_editor):

	Album = apps.get_model("beater", "Album")
	Artist = apps.get_model("beater", "Artist")

	for album in Album.objects.all():

		existing_artist = Artist.objects.filter(name=album.artist)

		if len(existing_artist) == 0:
			existing_artist = Artist(name=album.artist)
			existing_artist.save()
		else:
			existing_artist = existing_artist[0]

		album.artist_fk_id = existing_artist.id
		album.save()

def reverse_func(apps, schema_editor):

	pass

class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0003_album_artist_fk'),
    ]

    operations = [
    	migrations.RunPython(forwards_func, reverse_func)
    ]
