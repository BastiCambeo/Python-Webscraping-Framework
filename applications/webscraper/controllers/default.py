# -*- coding: utf-8 -*-

## Add tasks to menu ##
response.menu += (SPAN('Reload Tasks'), False, URL('ajax', 'add_tasks'),
                    [(task.name, False, URL('ajax', 'view_data', vars={"name": task.name})) for task in Task.query().fetch()]),

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

def task():
    task = Task.get(request.args.pop())
    response.title = task.name
    data = task.get_results(with_title=True)
    return dict(data=data, task=task)

def test():
    for task in Task.example_tasks():
        task.put()