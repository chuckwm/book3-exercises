# -*- coding: utf-8 -*-
# Generated by Django 1.9.9 on 2016-11-06 18:24
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_unpaidusers'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='rank',
            field=models.CharField(default='Padwan', max_length=50),
        ),
        migrations.AlterField(
            model_name='unpaidusers',
            name='last_notification',
            field=models.DateTimeField(default=datetime.datetime(2016, 11, 6, 18, 24, 32, 35490, tzinfo=utc)),
        ),
    ]