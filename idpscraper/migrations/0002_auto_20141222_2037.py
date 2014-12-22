# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('idpscraper', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='result',
            name='task_key',
        ),
        migrations.DeleteModel(
            name='Result',
        ),
        migrations.DeleteModel(
            name='Selector',
        ),
        migrations.RemoveField(
            model_name='urlselector',
            name='task_key',
        ),
        migrations.DeleteModel(
            name='Task',
        ),
        migrations.DeleteModel(
            name='UrlSelector',
        ),
    ]
