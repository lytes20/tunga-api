# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-15 07:17
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0022_auto_20160715_0208'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='invoice_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
