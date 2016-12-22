# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-12-19 04:45
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_utils', '0007_contactrequest_item'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contactrequest',
            name='item',
            field=models.CharField(blank=True, choices=[(b'self_guided', 'Do-it-yourself'), (b'onboarding', 'Tunga onboarding'), (b'onboarding_special', 'Onboarding special offer'), (b'project', 'Tunga project')], help_text='self_guided - Do-it-yourself,onboarding - Tunga onboarding,onboarding_special - Onboarding special offer,project - Tunga project', max_length=50, null=True),
        ),
    ]
