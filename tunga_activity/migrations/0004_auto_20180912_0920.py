# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-09-12 09:20
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_activity', '0003_auto_20180821_0952'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='notificationreadlog',
            options={'ordering': ['-created_at']},
        ),
    ]
