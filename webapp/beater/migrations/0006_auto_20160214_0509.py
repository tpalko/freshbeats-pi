# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0005_auto_20151031_1507'),
    ]

    operations = [
        migrations.RenameField(
            model_name='album',
            old_name='artist_fk',
            new_name='artist',
        ),
    ]
