# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-26 05:02
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0008_auto_20160525_2007'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='apply_closed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
