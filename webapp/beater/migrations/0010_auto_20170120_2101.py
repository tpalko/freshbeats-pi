# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-01-20 21:01
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0009_auto_20160514_0431'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='song',
            options={'ordering': ('name',)},
        ),
        migrations.AddField(
            model_name='album',
            name='request_priority',
            field=models.IntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='album',
            name='action',
            field=models.CharField(choices=[('checkin', 'Check-In'), ('refresh', 'Refresh'), ('checkout', 'Check-Out'), ('donothing', 'Do Nothing')], max_length=20, null=True),
        ),
    ]
