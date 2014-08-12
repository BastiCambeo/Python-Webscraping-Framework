# -*- coding: utf-8 -*-
__author__ = 'Sebastian Hofstetter'

@gae_taskqueue
def run_task():
    task = ndb.Key(urlsafe=request.vars.task_key).get()
    task.run(request.vars.url)

@gae_taskqueue
def schedule():
    start_cursor = ndb.Cursor(urlsafe=request.vars.start_cursor) if request.vars.start_cursor else None
    Task.get(request.vars.name).schedule(Query_Options(start_cursor=start_cursor))

session.forget()