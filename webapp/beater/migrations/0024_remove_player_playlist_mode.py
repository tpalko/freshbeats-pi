# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-02-18 04:18
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0023_playlistsong_last_played_at'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='player',
            name='playlist_mode',
        ),
    ]