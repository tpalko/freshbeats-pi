# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0008_album_sha1sum'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='album',
            name='sha1sum',
        ),
        migrations.AddField(
            model_name='song',
            name='sha1sum',
            field=models.CharField(max_length=40, null=True),
        ),
    ]
