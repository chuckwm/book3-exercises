# -*- coding: utf-8 -*-
# Generated by Django 1.9.9 on 2017-01-02 17:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0005_bigcoId_migration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='bigCoID',
            field=models.CharField(max_length=50, unique=True),
        ),
    ]