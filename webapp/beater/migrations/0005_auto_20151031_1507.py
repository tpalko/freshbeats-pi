# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0004_auto_20151031_1502'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='album',
            name='artist',
        ),
    ]
