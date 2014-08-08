# -*- coding: utf-8 -*-
__author__ = 'Sebastian Hofstetter'

def run_task():
    task = ndb.Key(urlsafe=request.vars.task_key).get()
    task.run(request.vars.url)