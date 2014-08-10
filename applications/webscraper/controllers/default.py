# -*- coding: utf-8 -*-
__author__ = 'Sebastian Hofstetter'

#########################################################################
## this is the main application menu add/remove items as required
#########################################################################
response.menu = [
    (T('Administration'), False, URL('admin', 'default', 'site')),
    (T('Appstats'), False, URL('_ah', 'stats')),
]
import os
from google.appengine.api import taskqueue
statistics = taskqueue.Queue(name="task").fetch_statistics()
tasks_status = "%s remaining Tasks  %s Tasks finished last minute" % (statistics.tasks, statistics.executed_last_minute or 0)

if 'SERVER_SOFTWARE' in os.environ and os.environ['SERVER_SOFTWARE'].find('Development') >= 0:  # is local?
    response.menu += [(T('Datastore Viewer'), False, '//localhost:8000/datastore')]
    response.menu += [(tasks_status, False, '//localhost:8000/taskqueue')]
else:
    response.menu += [(T('Database Viewer'), False, 'https://appengine.google.com/datastore/explorer?&app_id=s~idpscraper')]
    response.menu += [(T('Database Admin'), False, 'https://ah-builtin-python-bundle-dot-idpscraper.appspot.com/_ah/datastore_admin/?app_id=s~idpscraper&adminconsolecustompage')]
    response.menu += [(tasks_status, False, 'https://appengine.google.com/queues?&app_id=s~idpscraper')]

@auth.requires_login()
def index():
    return dict(tasks=Task.query().fetch())

def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    http://..../[app]/default/user/manage_users (requires membership in
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    """
    return dict(form=auth())

def call():
    """
    exposes services. for example:
    http://..../[app]/default/call/jsonrpc
    decorate with @services.jsonrpc the functions to expose
    supports xml, json, xmlrpc, jsonrpc, amfrpc, rss, csv
    """
    return service()

@auth.requires_login()
def task():
    task = Task.get(request.vars.name)
    response.title = task.name

    data = task.get_results(as_table=True)

    return dict(data=data, task=task)
