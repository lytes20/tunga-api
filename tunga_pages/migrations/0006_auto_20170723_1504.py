# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-07-23 15:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_pages', '0005_auto_20170723_1007'),
    ]

    operations = [
        migrations.AlterField(
            model_name='skillpage',
            name='welcome_header',
            field=models.CharField(max_length=70),
        ),
    ]