# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-07-24 05:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_pages', '0006_auto_20170723_1504'),
    ]

    operations = [
        migrations.AlterField(
            model_name='skillpage',
            name='welcome_sub_header',
            field=models.CharField(max_length=150),
        ),
    ]
