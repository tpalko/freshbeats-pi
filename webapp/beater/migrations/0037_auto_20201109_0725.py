# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-11-09 07:25
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0036_auto_20201101_0133'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='percent_pos',
            field=models.DecimalField(decimal_places=0, default=0, max_digits=4),
        ),
        migrations.AddField(
            model_name='player',
            name='time_pos',
            field=models.DecimalField(decimal_places=0, default=0, max_digits=4),
        ),
        migrations.AddField(
            model_name='player',
            name='time_remaining',
            field=models.DecimalField(decimal_places=0, default=0, max_digits=4),
        ),
    ]