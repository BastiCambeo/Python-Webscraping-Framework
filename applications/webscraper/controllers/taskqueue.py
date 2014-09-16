# -*- coding: utf-8 -*-
__author__ = 'Sebastian Hofstetter'

import json  # json support
import traceback

def run_task():
    url = request.vars.url
    schedule_id = request.vars.schedule_id

    Task.get(request.vars.name).run(schedule_id=schedule_id, url=url)
