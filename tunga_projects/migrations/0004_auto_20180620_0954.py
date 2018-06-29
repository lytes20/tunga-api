# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-06-20 09:54
from __future__ import unicode_literals

from django.db import migrations, models
import tagulous.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_projects', '0003_auto_20180619_0246'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='project',
            options={'ordering': ['-created_at']},
        ),
        migrations.AddField(
            model_name='participation',
            name='responded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='participation',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='skills',
            field=tagulous.models.fields.TagField(_set_tag_meta=True, blank=True, help_text='Enter a comma-separated tag string', initial='PHP, JavaScript, Python, Ruby, Java, C#, C++, Ruby, Swift, Objective C, .NET, ASP.NET, Node.js,HTML, CSS, HTML5, CSS3, XML, JSON, YAML,Django, Ruby on Rails, Flask, Yii, Lavarel, Express.js, Spring, JAX-RS,AngularJS, React.js, Meteor.js, Ember.js, Backbone.js,WordPress, Joomla, Drupal,jQuery, jQuery UI, Bootstrap, AJAX,Android, iOS, Windows Mobile, Apache Cordova, Ionic,SQL, MySQL, PostgreSQL, MongoDB, CouchDB,Git, Subversion, Mercurial, Docker, Ansible, Webpack, Grunt, Gulp, Ant, Maven, Gradle', space_delimiter=False, to='tunga_profiles.Skill'),
        ),
    ]