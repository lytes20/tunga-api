# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-23 00:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0096_task_survey_client'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='survey_client',
            field=models.BooleanField(default=True),
        ),
    ]
