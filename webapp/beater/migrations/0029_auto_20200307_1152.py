# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-03-07 11:52
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0028_auto_20200307_1150'),
    ]

    operations = [
        migrations.RenameField(
            model_name='player',
            old_name='beatlayer_registered',
            new_name='beatplayer_registered',
        ),
        migrations.RenameField(
            model_name='player',
            old_name='beatlayer_status',
            new_name='beatplayer_status',
        ),
        migrations.RenameField(
            model_name='player',
            old_name='beatlayer_volume',
            new_name='beatplayer_volume',
        ),
    ]
