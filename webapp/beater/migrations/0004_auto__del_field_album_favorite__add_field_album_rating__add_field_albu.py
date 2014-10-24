# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Album.favorite'
        db.delete_column(u'beater_album', 'favorite')

        # Adding field 'Album.rating'
        db.add_column(u'beater_album', 'rating',
                      self.gf('django.db.models.fields.CharField')(default='unrated', max_length=20),
                      keep_default=False)

        # Adding field 'Album.action'
        db.add_column(u'beater_album', 'action',
                      self.gf('django.db.models.fields.CharField')(max_length=20, null=True),
                      keep_default=False)


    def backwards(self, orm):
        # Adding field 'Album.favorite'
        db.add_column(u'beater_album', 'favorite',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Deleting field 'Album.rating'
        db.delete_column(u'beater_album', 'rating')

        # Deleting field 'Album.action'
        db.delete_column(u'beater_album', 'action')


    models = {
        u'beater.album': {
            'Meta': {'object_name': 'Album'},
            'action': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True'}),
            'artist': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'rating': ('django.db.models.fields.CharField', [], {'default': "'unrated'", 'max_length': '20'}),
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