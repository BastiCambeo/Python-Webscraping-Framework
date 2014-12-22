# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('idpscraper', '0003_auto_20141222_2056'),
    ]

    operations = [
        migrations.RenameField(
            model_name='result',
            old_name='task_key',
            new_name='task',
        ),
        migrations.RenameField(
            model_name='selector',
            old_name='task_key',
            new_name='task',
        ),
        migrations.RenameField(
            model_name='urlselector',
            old_name='task_key',
            new_name='task',
        ),
        migrations.RemoveField(
            model_name='task',
            name='creation_datetime',
        ),
    ]
