# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-03-07 11:38
from __future__ import unicode_literals

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0026_remove_player_beatplayer_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='created_at',
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
        migrations.AddField(
            model_name='player',
            name='preceding_command',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='player',
            name='preceding_command_args',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='player',
            name='repeat_song',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='player',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]