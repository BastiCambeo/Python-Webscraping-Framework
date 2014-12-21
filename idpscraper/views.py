from django.shortcuts import render
from django.utils import timezone
from django.http import HttpResponseRedirect, HttpResponse
from idpscraper.models.task import Task
from django.contrib import messages
import json


def index(request):
    messages.info(request, 'Hello world.')
    return render(request, 'idpscraper/index.html', dict(tasks=Task.objects.all()))


def task():
    task = Task.get(request.vars.name)
    data = task.get_results_as_table(Query_Options(limit=50))
    return dict(task=task, data=data)


def console(request):
    return render(request, 'idpscraper/console.html')


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


def spieler_details():
    from collections import Counter

    injury_counts = Counter([result.spieler_id for result in ndb.Key(Task, "Fussball_Verletzungen").get().get_results()])
    task = ndb.Key(Task, "Fussball_Spieler_Details").get()
    data = [tuple(selector.name for selector in task.selectors) + ("injury_count",)]
    for result in task.get_results():
        data.append(tuple(getattr(result, selector.name) for selector in task.selectors) + (injury_counts[result.spieler_id], ))
    response.headers["Content-Type"] = "application/vnd.ms-excel"
    return Task.export_data_to_excel(data)


def injuries_in_player_seasons():
    """ Remove all injuries that are not in the season in which a player played """
    injuries = Task.get("Fussball_Verletzungen").get_results()  # get all injuries
    del_injury_keys = []
    put_injuries = []
    players = set("%s %s" % (player.spieler_id, player.saison) for player in Task.get("Fussball_Spieler").get_results())  # get all players with seasons
    for injury in injuries:
        injury.season = (getattr(injury, "from") - timedelta(weeks=26)).year
        if "%s %s" % (injury.spieler_id, injury.season) in players:
            put_injuries.append(injury)
        else:
            del_injury_keys.append(injury.key)
    ndb.put_multi(put_injuries)
    ndb.delete_multi(del_injury_keys)


def injuries_in_action():
    """ Determine if an injury occured in action:= a match was scheduled for the same day or the day before """
    injuries = Result.query(Result.task_key == ndb.Key(Task, "Fussball_Verletzungen")).fetch()
    matches_same_day = [bool(match) for match in ndb.get_multi([ndb.Key("Result", "Fussball_Einsaetze%s %s" % (injury.spieler_id, getattr(injury, "from"))) for injury in injuries])]
    matches_day_before = [bool(match) for match in ndb.get_multi([ndb.Key("Result", "Fussball_Einsaetze%s %s" % (injury.spieler_id, getattr(injury, "from") + timedelta(days=-1))) for injury in injuries])]
    put_injuries = []
    for i in range(len(injuries)):
        if matches_same_day[i] or matches_day_before[i]:
            injuries[i].in_action = 1
            put_injuries.append(injuries[i])

    ndb.put_multi(put_injuries)
    return "%s %s" % (any(matches_same_day), any(matches_day_before))


def injuries_per_day():
    return repr([dict(id=injury.spieler_id, begin=getattr(injury, "from"), end=injury.to) for injury in Result.query(Result.task_key == ndb.Key(Task, "Fussball_Verletzungen")).fetch() if injury.to])


def test_task():
    try:
        results = Task.get(request.vars.name).test()[:30]
        return json.dumps(
            {"results": "<br>".join([repr(result._to_dict(exclude=["task_key"])) for result in results])})
    except Exception as e:
        traceback.print_exc()
        return json.dumps({"results": e.message})


def schedule_task():
    try:
        Task.get(request.vars.name).schedule()
        return json.dumps({})
    except Exception as e:
        traceback.print_exc()
        return json.dumps({"results": e.message})


def delete_results():
    return Task.get(request.vars.name).delete_results()


def export_excel():
    name = request.vars.name
    task = Task.get(name)
    response.headers["Content-Type"] = "application/vnd.ms-excel"
    return task.export_to_excel()


def export_gcs():
    name = request.vars.name
    task = Task.get(name)
    redirect(task.export_to_gcs())


def get_data():
    name = request.vars.name
    task = Task.get(name)
    query_options = Query_Options()

    if request.vars.limit:
        query_options.limit = int(request.vars.limit)
    if request.vars.cursor:
        query_options.cursor = ndb.Cursor(urlsafe=request.vars.cursor)
    elif request.vars.offset:
        query_options.offset = int(request.vars.offset)

    results = task.get_results_as_table(query_options=query_options)
    # results = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % value for value in row) for row in results)
    results = "\n".join("\t".join("%s" % (value if value is not None else "") for value in row) for row in results) + "\n"
    return json.dumps(dict(results=results, cursor=query_options.cursor.urlsafe() if query_options.cursor else "", has_next=query_options.has_next))


def get_gcs_data():
    name = request.vars.name
    task = Task.get(name)
    redirect(task.get_gcs_link())


def export_task():
    name = request.vars.name
    task = Task.get(name)
    response.headers["Content-Type"] = "text/plain"
    return task.export()


def delete_task():
    Task.get(request.vars.name).delete()


def new_task():
    task_name = request.vars.name
    assert not Task.get(task_name)  # Disallow overwriting of existing tasks
    Task(name=task_name).put()
    redirect("/webscraper/default/task?name=%s" % task_name)


def save_task():
    """ Takes the post request from the task form and saves the values to the task """
    task = Task.get(request.vars.task_name)
    task.url_selectors = [UrlSelector(
        url_raw=request.vars.getlist("url_raw[]")[i],
        task_key=ndb.Key(Task, request.vars.getlist("url_results_id[]")[i]),
        selector_name=request.vars.getlist("url_selector_names1[]")[i],
        selector_name2=request.vars.getlist("url_selector_names2[]")[i],
    ) for i in range(len(request.vars.getlist("url_raw[]")))]
    task.selectors = [Selector(
        is_key=unicode(i) in request.vars.selector_is_key,
        name=request.vars.getlist("selector_name[]")[i],
        xpath=request.vars.getlist("selector_xpath[]")[i],
        type=Selector.TYPES[int(request.vars.getlist("selector_type[]")[i])],
        regex=request.vars.getlist("selector_regex[]")[i],
    ) for i in range(len(request.vars.getlist("selector_name[]")))]
    task.put()


def get_task_selector_names():
    return json.dumps([selector.name for selector in Task.get(request.vars.name).selectors])


def result_count():
    i = 0
    for key in Result.query().fetch(keys_only=True):
        i += 1
    return i


def put_tasks():
    ndb.put_multi(Task.example_tasks())
    redirect("/")


def run_command():
    try:
        return json.dumps({"results": repr(eval(request.vars.command))})
    except Exception as e:
        traceback.print_exc()
        return json.dumps({"results": e.message})


def export_all_tasks():
    response.headers["Content-Type"] = "text/plain"
    return ",\n".join([task.export() for task in Task.query().fetch()])