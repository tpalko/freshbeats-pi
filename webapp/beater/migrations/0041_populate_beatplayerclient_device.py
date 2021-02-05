# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-11-29 00:40
from __future__ import unicode_literals

from django.conf import settings 
from django.db import migrations

def forwards_func(apps, schema_editor):
    Device = apps.get_model("beater", "Device")
    default_device = Device.objects.filter(name='Default').first()
    if not default_device:
        default_device = Device.objects.create(name='Default', ip_address='192.168.1.2')
    
    BeatPlayerClient = apps.get_model("beater", "BeatPlayerClient")
    for client in BeatPlayerClient.objects.all():
        url_device = Device.objects.filter(agent_base_url=client.beatplayer_url).first()
        if url_device is None:
            new_device_name = 'Auto %s' % client.beatplayer_url
            url_device = Device.objects.create(name=new_device_name, ip_address='192.168.1.2')
        client.device = url_device 
        client.save()
    
def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0040_auto_20201128_1956'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]