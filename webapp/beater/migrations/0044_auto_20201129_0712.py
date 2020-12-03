# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-11-29 07:12
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0043_populate_player_device'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='last_health_check',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='device',
            name='mounted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='device',
            name='reachable',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='device',
            name='registered',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='device',
            name='registered_at',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='device',
            name='selfreport',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='device',
            name='status',
            field=models.CharField(choices=[('ready', 'Ready'), ('notready', 'Not Ready'), ('down', 'Down')], default='down', max_length=20),
        ),
        migrations.RunSQL('update beater_device d inner join beater_beatplayerclient c on c.device_id = d.id set d.last_health_check = c.last_health_check, d.status = c.status, d.reachable = c.reachable, d.registered = c.registered, d.mounted = c.mounted, d.selfreport = c.selfreport, d.registered_at = c.registered_at'),
    ]
