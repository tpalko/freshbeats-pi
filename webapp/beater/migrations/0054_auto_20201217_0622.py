# Generated by Django 2.2.17 on 2020-12-17 06:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0053_auto_20201211_2028'),
    ]

    operations = [
        migrations.AlterField(
            model_name='player',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
