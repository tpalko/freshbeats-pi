# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-12-01 19:24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0045_auto_20201129_0719'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='agent_base_url',
            field=models.CharField(max_length=255),
        ),
    ]
