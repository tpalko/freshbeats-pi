# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-12-08 18:53
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0049_auto_20201207_0801'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='parent',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='beater.Player'),
        ),
    ]
