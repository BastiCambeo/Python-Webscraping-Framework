# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('idpscraper', '0004_auto_20141222_2122'),
    ]

    operations = [
        migrations.RenameField(
            model_name='urlselector',
            old_name='url_raw',
            new_name='url',
        ),
    ]
