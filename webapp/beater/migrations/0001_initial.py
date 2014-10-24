# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Album'
        db.create_table(u'beater_album', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('artist', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('tracks', self.gf('django.db.models.fields.IntegerField')()),
            ('size', self.gf('django.db.models.fields.BigIntegerField')()),
        ))
        db.send_create_signal(u'beater', ['Album'])

        # Adding model 'AlbumCheckout'
        db.create_table(u'beater_albumcheckout', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('album', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['beater.Album'])),
            ('checkout_at', self.gf('django.db.models.fields.DateTimeField')()),
            ('return_at', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal(u'beater', ['AlbumCheckout'])


    def backwards(self, orm):
        # Deleting model 'Album'
        db.delete_table(u'beater_album')

        # Deleting model 'AlbumCheckout'
        db.delete_table(u'beater_albumcheckout')


    models = {
        u'beater.album': {
            'Meta': {'object_name': 'Album'},
            'artist': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'size': ('django.db.models.fields.BigIntegerField', [], {}),
            'tracks': ('django.db.models.fields.IntegerField', [], {})
        },
        u'beater.albumcheckout': {
            'Meta': {'object_name': 'AlbumCheckout'},
            'album': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['beater.Album']"}),
            'checkout_at': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'return_at': ('django.db.models.fields.DateTimeField', [], {})
        }
    }

    complete_apps = ['beater']