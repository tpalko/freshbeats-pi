# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Album',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('artist', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255)),
                ('tracks', models.IntegerField()),
                ('audio_size', models.BigIntegerField(default=0)),
                ('total_size', models.BigIntegerField(default=0)),
                ('old_total_size', models.BigIntegerField(null=True)),
                ('rating', models.CharField(default=b'unrated', max_length=20, choices=[(b'loveit', b'Love it'), (b'mixitup', b'Not my thing, but nice to mix it up'), (b'nothanks', b'Good, but OK if I never hear it again'), (b'notgood', b'Not good'), (b'undecided', b'Undecided'), (b'unrated', b'Unrated')])),
                ('action', models.CharField(max_length=20, null=True, choices=[(b'remove', b'Remove'), (b'update', b'Update'), (b'add', b'Add'), (b'donothing', b'Do Nothing')])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='AlbumCheckout',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('checkout_at', models.DateTimeField()),
                ('return_at', models.DateTimeField(null=True)),
                ('album', models.ForeignKey(on_delete=models.CASCADE, to='beater.Album')),
            ],
        ),
        migrations.CreateModel(
            name='AlbumStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status', models.CharField(max_length=20, choices=[(b'incomplete', b'The album is incomplete'), (b'mislabeled', b'The album is mislabeled'), (b'ripping problem', b'The album has ripping problems')])),
                ('album', models.ForeignKey(on_delete=models.CASCADE, to='beater.Album')),
            ],
        ),
        migrations.CreateModel(
            name='PlaylistSong',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_current', models.BooleanField(default=False)),
                ('played', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Song',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('album', models.ForeignKey(on_delete=models.CASCADE, to='beater.Album')),
            ],
        ),
        migrations.AddField(
            model_name='playlistsong',
            name='song',
            field=models.ForeignKey(on_delete=models.CASCADE, to='beater.Song'),
        ),
    ]
