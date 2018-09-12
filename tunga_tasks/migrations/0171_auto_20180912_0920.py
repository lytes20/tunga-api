# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-09-12 09:20
from __future__ import unicode_literals

from django.db import migrations
import tagulous.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0170_auto_20180807_0455'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='skills',
            field=tagulous.models.fields.TagField(_set_tag_meta=True, blank=True, help_text='Enter a comma-separated tag string', initial='Kampala, Entebbe, Jinja, Nairobi, Mombosa, Dar es Salaam, Kigali, Amsterdam', space_delimiter=False, to='tunga_profiles.Skill'),
        ),
    ]
