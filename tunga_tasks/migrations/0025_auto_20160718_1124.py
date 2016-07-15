# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-18 11:24
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import tunga_utils.validators


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0024_auto_20160715_1129'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParticipantPayment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('destination', models.CharField(max_length=40, validators=[tunga_utils.validators.validate_btc_address])),
                ('ref', models.CharField(max_length=255)),
                ('btc_sent', models.DecimalField(decimal_places=8, max_digits=10)),
                ('btc_received', models.DecimalField(decimal_places=8, default=0, max_digits=10)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending', help_text='pending - Pending, processing - Processing, completed - Completed, failed - Failed', max_length=30)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('received_at', models.DateTimeField(blank=True, null=True)),
                ('description', models.CharField(blank=True, max_length=200, null=True)),
                ('participant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tunga_tasks.Participation')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='TaskPayment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('btc_address', models.CharField(max_length=40, validators=[tunga_utils.validators.validate_btc_address])),
                ('ref', models.CharField(max_length=255)),
                ('btc_price', models.DecimalField(decimal_places=8, max_digits=10)),
                ('btc_received', models.DecimalField(decimal_places=8, default=0, max_digits=10)),
                ('processed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('received_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.RemoveField(
            model_name='task',
            name='btc_received',
        ),
        migrations.RemoveField(
            model_name='task',
            name='invoice_amount',
        ),
        migrations.AddField(
            model_name='task',
            name='btc_price',
            field=models.DecimalField(blank=True, decimal_places=8, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='taskpayment',
            name='task',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tunga_tasks.Task'),
        ),
        migrations.AddField(
            model_name='participantpayment',
            name='source',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tunga_tasks.TaskPayment'),
        ),
        migrations.AlterUniqueTogether(
            name='taskpayment',
            unique_together=set([('btc_address', 'ref')]),
        ),
        migrations.AlterUniqueTogether(
            name='participantpayment',
            unique_together=set([('destination', 'ref')]),
        ),
    ]
