# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2019-07-07 21:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0015_auto_20180711_2045'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Device',
        ),
        migrations.AddField(
            model_name='artist',
            name='followed',
            field=models.BooleanField(default=False),
        ),
    ]
