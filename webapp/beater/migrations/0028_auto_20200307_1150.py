# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-03-07 11:50
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0027_auto_20200307_1138'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='beatlayer_registered',
            field=models.NullBooleanField(),
        ),
        migrations.AddField(
            model_name='player',
            name='beatlayer_status',
            field=models.CharField(max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='player',
            name='beatlayer_volume',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='player',
            name='playlistsong',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='beater.PlaylistSong'),
        ),
    ]
