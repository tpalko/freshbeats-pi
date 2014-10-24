# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Album.status'
        db.delete_column(u'beater_album', 'status')


    def backwards(self, orm):
        # Adding field 'Album.status'
        db.add_column(u'beater_album', 'status',
                      self.gf('django.db.models.fields.CharField')(default='ok', max_length=20, null=True),
                      keep_default=False)


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
            'status': ('django.db.models.fields.CharField', [], {'default': "'ok'", 'max_length': '20', 'null': 'True'})
        },
        u'beater.song': {
            'Meta': {'object_name': 'Song'},
            'album': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['beater.Album']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['beater']