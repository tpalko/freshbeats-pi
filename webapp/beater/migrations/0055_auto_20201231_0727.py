# Generated by Django 2.2.17 on 2020-12-31 07:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beater', '0054_auto_20201217_0622'),
    ]

    operations = [
        migrations.AlterField(
            model_name='player',
            name='preceding_command_args',
            field=models.CharField(max_length=1024, null=True),
        ),
    ]
