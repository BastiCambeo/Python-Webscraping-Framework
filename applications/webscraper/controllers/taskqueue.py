# -*- coding: utf-8 -*-
__author__ = 'Sebastian Hofstetter'

@gae_taskqueue
def run_task():
    url = request.vars.url
    schedule_id = request.vars.schedule_id

    Task.get(request.vars.name).run(schedule_id=schedule_id, url=url)

    logging.info("Ran Task [%s seconds] %s" % ((datetime.now() - time_before_request).total_seconds(), url))  # For Debugging purposes

@gae_taskqueue
def delete_results():
    cursor = ndb.Cursor.from_websafe_string(request.vars.cursor) if request.vars.cursor else None
    Task.delete_all_results(cursor=cursor)

session.forget()
