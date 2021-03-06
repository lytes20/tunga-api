# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-12-08 07:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_auth', '0013_auto_20171129_0657'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tungauser',
            name='payoneer_status',
            field=models.CharField(choices=[(b'initial', 'Initial'), (b'pending', 'Pending'), (b'approved', 'Approved'), (b'declined', 'Decline')], default=b'initial', help_text='initial - Initial, pending - Pending, approved - Approved, declined - Decline', max_length=20),
        ),
    ]
