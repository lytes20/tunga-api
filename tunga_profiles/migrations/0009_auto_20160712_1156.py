# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-07-12 11:56
from __future__ import unicode_literals

from django.db import migrations, models
import tunga_utils.validators


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_profiles', '0008_auto_20160704_1841'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='btc_address',
            field=models.CharField(blank=True, max_length=40, null=True, validators=[tunga_utils.validators.validate_btc_address]),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='btc_wallet_provider',
            field=models.CharField(blank=True, choices=[('coinbase', 'Coinbase')], help_text='coinbase - Coinbase', max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='company_bio',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='company_profile',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='mobile_money_number',
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='payment_method',
            field=models.CharField(blank=True, choices=[('btc_wallet', 'Bitcoin Wallet'), ('btc_address', 'Bitcoin Address'), ('mobile_money', 'Mobile Money')], help_text='btc_wallet - Bitcoin Wallet,btc_address - Bitcoin Address,mobile_money - Mobile Money', max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='vat_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
