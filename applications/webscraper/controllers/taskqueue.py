# -*- coding: utf-8 -*-
__author__ = 'Sebastian Hofstetter'

def run_task():
    task = ndb.Key(urlsafe=request.vars.task_key).get()
    task.run(request.vars.url)

def schedule():
    start_cursor = ndb.Cursor(urlsafe=request.vars.start_cursor) if request.vars.start_cursor else None
    ndb.transaction(lambda : Task.get(request.vars.name).schedule(Query_Options(start_cursor=start_cursor)), xg=True)