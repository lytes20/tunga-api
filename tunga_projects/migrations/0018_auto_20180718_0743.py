# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-07-18 07:43
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_projects', '0017_auto_20180718_0741'),
    ]

    operations = [
        migrations.AlterField(
            model_name='progressreport',
            name='status',
            field=models.CharField(blank=True, choices=[(b'on_schedule', b'On schedule'), (b'behind', b'Behind'), (b'stuck', b'Stuck'), (b'behind_progressing', b'Behind but Progressing'), (b'behind_stuck', b'Behind and Stuck')], help_text='on_schedule - On schedule,behind - Behind,stuck - Stuck,behind_progressing - Behind but Progressing,behind_stuck - Behind and Stuck', max_length=50, null=True),
        ),
    ]
