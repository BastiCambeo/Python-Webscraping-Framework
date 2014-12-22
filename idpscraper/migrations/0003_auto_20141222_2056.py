# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('idpscraper', '0002_auto_20141222_2037'),
    ]

    operations = [
        migrations.CreateModel(
            name='Result',
            fields=[
                ('key', models.TextField(primary_key=True, serialize=False)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Selector',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID', auto_created=True)),
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
                ('name', models.TextField(primary_key=True, serialize=False)),
                ('creation_datetime', models.DateTimeField(auto_now_add=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UrlSelector',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID', auto_created=True)),
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
            model_name='selector',
            name='task_key',
            field=models.ForeignKey(to='idpscraper.Task'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='result',
            name='task_key',
            field=models.ForeignKey(to='idpscraper.Task'),
            preserve_default=True,
        ),
    ]
