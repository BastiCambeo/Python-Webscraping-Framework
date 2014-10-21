# -*- coding: utf-8 -*-
__author__ = 'Sebastian Hofstetter'

#########################################################################
## this is the main application menu add/remove items as required
#########################################################################
response.menu = [
    (T('Administration'), False, URL('admin', 'default', 'site')),
    (T('Appstats'), False, URL('_ah', 'stats')),
    (T('Console'), False, URL('default', 'console')),
]
import os
from google.appengine.api import taskqueue
statistics = taskqueue.Queue(name="task").fetch_statistics()
tasks_status = "%s remaining Tasks  %s Tasks finished last minute" % (statistics.tasks, statistics.executed_last_minute or 0)

if 'SERVER_SOFTWARE' in os.environ and os.environ['SERVER_SOFTWARE'].find('Development') >= 0:  # is local?
    response.menu += [(T('Datastore Viewer'), False, '//localhost:8000/datastore')]
    response.menu += [(tasks_status, False, '//localhost:8000/taskqueue')]
else:
    response.menu += [(T('Datastore Viewer'), False, 'https://appengine.google.com/datastore/explorer?&app_id=s~cambeotrunk')]
    response.menu += [(T('Datastore Admin'), False, 'https://ah-builtin-python-bundle-dot-cambeotrunk.appspot.com/_ah/datastore_admin/?app_id=s~cambeotrunk&adminconsolecustompage')]
    response.menu += [(tasks_status, False, 'https://appengine.google.com/queues?&app_id=s~cambeotrunk')]

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
    data = task.get_results_as_table(Query_Options(limit=500))

    return dict(data=data, task=task)

@auth.requires_login()
def console():
    return dict()

@cache.action(time_expire=999999999)
def relative_age():
    from collections import OrderedDict
    birthdays = OrderedDict()
    for month in ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]:
        birthdays[month] = 0

    for athlete in Result.query(ancestor=ndb.Key(Task, "Leichtathletik_Athleten")).fetch(10000):
        try:
            if not (athlete.birthday.day == 1 and athlete.birthday.month == 1):  # 1.1. is a dummy date for athletes where the exact birthday is unknown
                birthdays[athlete.birthday.strftime("%B")] += 1
        except:
            pass
    return dict(birthdays=birthdays)

@cache.action(time_expire=999999999)
def injuries():
    return BEAUTIFY(sorted(set(result.injury for result in Task.get("Fussball_Verletzungen").get_results())))

@cache.action(time_expire=999999999)
def spieler_details():
    from collections import Counter
    injury_counts = Counter([result.spieler_id for result in ndb.Key(Task, "Fussball_Verletzungen").get().get_results()])
    task = ndb.Key(Task, "Fussball_Spieler_Details").get()
    data = [tuple(selector.name for selector in task.selectors) + ("injury_count",)]
    for result in task.get_results():
        data.append(tuple(getattr(result, selector.name) for selector in task.selectors) + (injury_counts[result.spieler_id], ))
    response.headers["Content-Type"] = "application/vnd.ms-excel"
    return Task.export_data_to_excel(data)

def injuries_in_action():
    injury_keys = Task.get("Fussball_Verletzungen").get_results(query_options=Query_Options(keys_only=True))  # get all injuries
    game_keys = [ndb.Key("Result", "Fussball_Einsaetze" + injury_key.id()[21:]) for injury_key in injury_keys]  # get all games that correspond to an injury
    injury_keys = [ndb.Key("Result", "Fussball_Verletzungen" + game.key.id()[18:]) for game in ndb.get_multi(game_keys) if game]
    injuries = ndb.get_multi(injury_keys)
    for injury in injuries:
        injury.in_action = 1
    ndb.put_multi(injuries)
    injuries = ndb.get_multi(injury_keys)
    return BEAUTIFY(injuries)

def top_performance():
    limit = int(request.vars.limit) if request.vars.limit else None
    offset = int(request.vars.offset) if request.vars.offset else None
    return TABLE(list(Task.get("Leichtathletik_Top_Performance").get_results_as_table(query_options=Query_Options(limit=limit, offset=offset))))