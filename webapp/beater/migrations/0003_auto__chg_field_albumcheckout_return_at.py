# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'AlbumCheckout.return_at'
        db.alter_column(u'beater_albumcheckout', 'return_at', self.gf('django.db.models.fields.DateTimeField')(null=True))

    def backwards(self, orm):

        # User chose to not deal with backwards NULL issues for 'AlbumCheckout.return_at'
        raise RuntimeError("Cannot reverse this migration. 'AlbumCheckout.return_at' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration
        # Changing field 'AlbumCheckout.return_at'
        db.alter_column(u'beater_albumcheckout', 'return_at', self.gf('django.db.models.fields.DateTimeField')())

    models = {
        u'beater.album': {
            'Meta': {'object_name': 'Album'},
            'artist': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'favorite': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
            'return_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'})
        },
        u'beater.song': {
            'Meta': {'object_name': 'Song'},
            'album': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['beater.Album']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['beater']