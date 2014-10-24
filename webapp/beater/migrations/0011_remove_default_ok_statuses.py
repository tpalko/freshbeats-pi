# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def forwards(self, orm):
        "Write your forwards methods here."
        # Note: Don't use "from appname.models import ModelName". 
        # Use orm.ModelName to refer to models in this application,
        # and orm['appname.ModelName'] for models in other applications.

	db.execute("delete from beater_albumstatus where status = 'ok'")

    def backwards(self, orm):
        "Write your backwards methods here."

    models = {
        u'beater.album': {
            'Meta': {'object_name': 'Album'},
            'action': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True'}),
            'artist': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'old_size': ('django.db.models.fields.BigIntegerField', [], {}),
            'rating': ('django.db.models.fields.CharField', [], {'default': "'unrated'", 'max_length': '20'}),
            'size': ('django.db.models.fields.BigIntegerField', [], {}),
            'tracks': ('django.db.models.fields.IntegerField', [], {}),
            'updated_at': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        u'beater.albumcheckout': {
            'Meta': {'object_name': 'AlbumCheckout'},
            'album': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['beater.Album']"}),
            'checkout_at': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'return_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'})
        },
        u'beater.albumstatus': {
            'Meta': {'object_name': 'AlbumStatus'},
            'album': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['beater.Album']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        },
        u'beater.song': {
            'Meta': {'object_name': 'Song'},
            'album': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['beater.Album']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['beater']
    symmetrical = True
