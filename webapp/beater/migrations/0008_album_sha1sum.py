# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0007_album_sticky'),
    ]

    operations = [
        migrations.AddField(
            model_name='album',
            name='sha1sum',
            field=models.CharField(max_length=40, null=True),
        ),
    ]
