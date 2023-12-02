# Generated by Django 2.0.13 on 2022-02-14 07:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0069_auto_20220214_0355'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='album',
            name='action',
        ),
        migrations.RemoveField(
            model_name='album',
            name='request_priority',
        ),
        migrations.AddField(
            model_name='mobile',
            name='ip_address',
            field=models.GenericIPAddressField(null=True, protocol='IPv4'),
        ),
        migrations.AddField(
            model_name='mobile',
            name='ssh_private_key_path',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='mobile',
            name='ssh_username',
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='mobile',
            name='target_path',
            field=models.CharField(default='/media', max_length=255),
            preserve_default=False,
        ),
    ]