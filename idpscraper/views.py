from django.shortcuts import render
from django.utils import timezone
from django.http import HttpResponseRedirect, HttpResponse
from idpscraper.models import Task, Selector, UrlSelector, Result, serialize
from django.contrib import messages
from django.core.urlresolvers import reverse
import json
import traceback
from idpscraper.models.template import render as render2


def index(request):
    return render(request, 'idpscraper/index.html', dict(tasks=Task.objects.all()))


def task(request, name):
    task = Task.get(name)
    data = task.as_table(task.results.all())
    all_tasks = Task.objects.all()
    return render(request, 'idpscraper/task.html', dict(task=task, data=data, all_tasks=all_tasks, selector_choices=Selector.TYPE_CHOICES))


def console(request):
    return render(request, 'idpscraper/console.html')


def test(request):
    return HttpResponse(render2(filename="idpscraper/templates/idpscraper/test.html"))


def relative_age(request):
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


def injuries_in_player_seasons(request):
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


def injuries_in_action(request):
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


def injuries_per_day(request):
    return repr([dict(id=injury.spieler_id, begin=getattr(injury, "from"), end=injury.to) for injury in Result.query(Result.task_key == ndb.Key(Task, "Fussball_Verletzungen")).fetch() if injury.to])


def test_task(request, name):
    try:
        task = Task.get(name)
        results = task.test()[:30]
        results = "<br>".join((" ".join(str(cell) for cell in row) for row in task.as_table(results)))
        return HttpResponse(json.dumps(dict(results=results)), content_type="application/json")
    except Exception as e:
        traceback.print_exc()
        return HttpResponse(json.dumps(dict(results=str(e))), content_type="application/json")


def run_task(request, name):
    try:
        Task.get(name).run()
        return HttpResponse(json.dumps(dict()), content_type="application/json")
    except Exception as e:
        traceback.print_exc()
        return HttpResponse(json.dumps(dict(results=str(e))), content_type="application/json")


def delete_results(request, name):
    task = Task.get(name)
    Result.objects.filter(task=task).delete()
    return HttpResponse(json.dumps(dict()), content_type="application/json")


def export_excel(request, name):
    task = Task.get(name)
    return HttpResponse(task.export_to_excel(), content_type="application/vnd.ms-excel")


def export_task(request, name):
    task = Task.get(name)
    return HttpResponse(task.export(), content_type="text/plain")


def delete_task(request, name):
    Task.get(name).delete()
    return HttpResponse(json.dumps(dict()), content_type="application/json")


def new_task(request):
    name = request.POST["name"]
    Task(name=name).save()
    UrlSelector(task_id=name, selector_task_id=name).save()
    Selector(task_id=name).save()
    return HttpResponse(json.dumps(dict()), content_type="application/json")


def save_task(request, name):
    """ Takes the post request from the task form and saves the values to the task """
    task = Task.get(name)

    UrlSelector.objects.filter(task=task).delete()
    url_selectors = [UrlSelector(
        task_id=name,
        url=request.POST.getlist("url[]")[i],
        selector_task_id=request.POST.getlist("url_results_id[]")[i],
        selector_name=request.POST.getlist("url_selector_name[]")[i],
        selector_name2=request.POST.getlist("url_selector_name2[]")[i],
    ) for i in range(len(request.POST.getlist("url[]")))]
    UrlSelector.objects.bulk_create(url_selectors)

    Selector.objects.filter(task=task).delete()
    selectors = [Selector(
        task_id=name,
        is_key=str(i) in request.POST.getlist("selector_is_key"),
        name=request.POST.getlist("selector_name[]")[i],
        xpath=request.POST.getlist("selector_xpath[]")[i],
        type=int(request.POST.getlist("selector_type[]")[i]),
        regex=request.POST.getlist("selector_regex[]")[i],
    ) for i in range(len(request.POST.getlist("selector_name[]")))]
    Selector.objects.bulk_create(selectors)

    return HttpResponse(json.dumps(dict()), content_type="application/json")


def get_task_selectors(request, name):
    task = Task.get(name)
    selectors = list(task.selectors.all())
    return HttpResponse(json.dumps(selectors, default=serialize.serialize), content_type="application/json")


def put_tasks(request):
    Task.example_tasks()
    return HttpResponseRedirect(reverse("idpscraper:index"))


def run_command(request):
    try:
        return json.dumps({"results": repr(eval(request.vars.command))})
    except Exception as e:
        return json.dumps({"results": str(e)})
