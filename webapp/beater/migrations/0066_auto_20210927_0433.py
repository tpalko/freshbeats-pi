# Generated by Django 2.0 on 2021-09-27 04:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0065_auto_20210927_0200'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='player',
            name='beatplayer_registered',
        ),
        migrations.AddField(
            model_name='player',
            name='beatplayer_registered_at',
            field=models.DateTimeField(null=True),
        ),
    ]
