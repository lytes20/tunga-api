# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2018-04-12 09:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_pages', '0021_auto_20180412_0954'),
    ]

    operations = [
        migrations.AddField(
            model_name='skillpage',
            name='meta_keywords',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
