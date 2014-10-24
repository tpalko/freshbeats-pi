# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Album.old_size'
        db.delete_column(u'beater_album', 'old_size')

        # Adding field 'Album.total_size'
        db.add_column(u'beater_album', 'total_size',
                      self.gf('django.db.models.fields.BigIntegerField')(default=0),
                      keep_default=False)

        # Adding field 'Album.old_total_size'
        db.add_column(u'beater_album', 'old_total_size',
                      self.gf('django.db.models.fields.BigIntegerField')(null=True),
                      keep_default=False)


    def backwards(self, orm):

        # User chose to not deal with backwards NULL issues for 'Album.old_size'
        raise RuntimeError("Cannot reverse this migration. 'Album.old_size' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'Album.old_size'
        db.add_column(u'beater_album', 'old_size',
                      self.gf('django.db.models.fields.BigIntegerField')(),
                      keep_default=False)

        # Deleting field 'Album.total_size'
        db.delete_column(u'beater_album', 'total_size')

        # Deleting field 'Album.old_total_size'
        db.delete_column(u'beater_album', 'old_total_size')


    models = {
        u'beater.album': {
            'Meta': {'object_name': 'Album'},
            'action': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True'}),
            'artist': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'audio_size': ('django.db.models.fields.BigIntegerField', [], {'default': '0'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'old_total_size': ('django.db.models.fields.BigIntegerField', [], {'null': 'True'}),
            'rating': ('django.db.models.fields.CharField', [], {'default': "'unrated'", 'max_length': '20'}),
            'total_size': ('django.db.models.fields.BigIntegerField', [], {'default': '0'}),
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