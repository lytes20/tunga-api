# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-09-12 09:20
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_projects', '0026_auto_20180911_2328'),
    ]

    operations = [
        migrations.AddField(
            model_name='interestpoll',
            name='token',
            field=models.UUIDField(default=uuid.uuid4),
        ),
    ]
