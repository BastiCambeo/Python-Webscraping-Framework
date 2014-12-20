# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Result',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Selector',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),
                ('name', models.TextField()),
                ('type', models.IntegerField()),
                ('xpath', models.TextField()),
                ('regex', models.TextField(blank=True)),
                ('is_key', models.BooleanField(default=False)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('name', models.TextField(serialize=False, primary_key=True)),
                ('creation_datetime', models.DateTimeField(auto_now_add=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UrlSelector',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),
                ('url_raw', models.TextField()),
                ('selector_name', models.TextField()),
                ('selector_name2', models.TextField()),
                ('task_key', models.ForeignKey(to='idpscraper.Task')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='result',
            name='task_key',
            field=models.ForeignKey(to='idpscraper.Task'),
            preserve_default=True,
        ),
    ]
