# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0006_auto_20160214_0509'),
    ]

    operations = [
        migrations.AddField(
            model_name='album',
            name='sticky',
            field=models.BooleanField(default=False),
        ),
    ]
