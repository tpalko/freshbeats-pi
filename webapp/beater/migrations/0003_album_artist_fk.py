# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0002_artist'),
    ]

    operations = [
        migrations.AddField(
            model_name='album',
            name='artist_fk',
            field=models.ForeignKey(to='beater.Artist', null=True),
        ),
    ]
