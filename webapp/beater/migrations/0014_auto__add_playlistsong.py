# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'PlaylistSong'
        db.create_table(u'beater_playlistsong', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('song', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['beater.Song'])),
            ('is_current', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal(u'beater', ['PlaylistSong'])


    def backwards(self, orm):
        # Deleting model 'PlaylistSong'
        db.delete_table(u'beater_playlistsong')


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
        u'beater.playlistsong': {
            'Meta': {'object_name': 'PlaylistSong'},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_current': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'song': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['beater.Song']"})
        },
        u'beater.song': {
            'Meta': {'object_name': 'Song'},
            'album': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['beater.Album']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['beater']