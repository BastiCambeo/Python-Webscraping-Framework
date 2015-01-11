from django.shortcuts import render
from django.utils import timezone
from django.http import HttpResponseRedirect, HttpResponse
from idpscraper.models import Task, Selector, UrlSelector, Result, serialize
from django.contrib import messages
from django.core.urlresolvers import reverse
from collections import defaultdict
import json
import traceback
import datetime
from idpscraper.models.template import render as render2


def index(request):
    return render(request, 'idpscraper/index.html', dict(tasks=Task.objects.all()))


def task(request, name):
    task = Task.get(name)
    data = task.as_table(task.results.all()[:50])
    all_tasks = Task.objects.all()
    return render(request, 'idpscraper/task.html', dict(task=task, data=data, all_tasks=all_tasks, selector_choices=Selector.TYPE_CHOICES))


def console(request):
    return render(request, 'idpscraper/console.html')


def test(request):
    #  missing = [42787, 32711, 32713, 24463, 3568, 58864, 24465, 32719, 54964, 93584, 28150, 695, 45464, 72792, 162652, 42942, 68574]
    missing = [93584, 72792, 68574, 54964, 42787, 32719, 32713, 24465]
    task = Task.get("Football_Player_Details")
    results = task.results.all()
    results = [result for result in results if result.player_id in missing]
    #  results = [Result(results=dict(player_id=1, name="name", position="position", birthday=datetime.datetime.now(), size=2.2, retire_date=datetime.datetime.now()))]
    return HttpResponse(Task.export_data_to_excel(task.as_table(results)), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def relative_age(request):
    from collections import OrderedDict

    birthdays = OrderedDict()
    for month in ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]:
        birthdays[month] = 0

    athletes = {athlete.athlete_id: athlete for athlete in Task.get("Leichtathletik_Top_Performance").results.all()}

    for athlete in athletes.values():
        try:
            if not (athlete.birthday.day == 1 and athlete.birthday.month == 1):  # 1.1. is a dummy date for athletes where the exact birthday is unknown
                birthdays[athlete.birthday.strftime("%B")] += 1
        except:
            pass
    return render(request, 'idpscraper/relative_age.html', dict(birthdays=birthdays, considered_athlete_count=sum(birthdays.values()), athlete_count=len(athletes)))


def relative_age2(request):
    from collections import OrderedDict

    birthdays = OrderedDict()
    for month in ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]:
        birthdays[month] = 0

    athletes = {athlete.spieler_id: athlete for athlete in Task.get("Fussball_Spieler_Details").results.all()}

    for athlete in athletes.values():
        try:
            # 1.1. is not a dummy date for players, because of the high quality of the database
            birthdays[athlete.birthday.strftime("%B")] += 1
        except:
            pass
    return render(request, 'idpscraper/relative_age.html', dict(birthdays=birthdays, considered_athlete_count=sum(birthdays.values()), athlete_count=len(athletes)))


def injuries_in_player_seasons(request):
    """ Remove all injuries and matches that are not in the season in which a player played """
    Selector.objects.filter(task_id="Football_Injuries", name="season").delete()
    Selector(task_id="Football_Injuries", name="season", type=Selector.INTEGER).save()
    Selector.objects.filter(task_id="Football_Matches", name="season").delete()
    Selector(task_id="Football_Matches", name="season", type=Selector.INTEGER).save()

    injuries = Task.get("Football_Injuries").results.all()  # get all injuries
    matches = Task.get("Football_Matches").results.all()  # get all matches
    players = set((player.player_id, player.season) for player in Task.get("Football_Players").results.all())  # get all players with seasons

    # update injuries #
    for injury in injuries:
        injury.season = (injury.begin - datetime.timedelta(weeks=26)).year
        if (injury.player_id, injury.season) in players:
            injury.save()
        else:
            injury.delete()

    # update matches #
    for match in matches:
        match.season = (match.date - datetime.timedelta(weeks=26)).year
        if (match.player_id, match.season) in players:
            match.save()
        else:
            match.delete()

    return HttpResponse("finished")


def injuries_in_action(request):
    """ Determine if an injury occured in action:= the injury ocurred on a match day, or the day after """
    Selector.objects.filter(task_id="Football_Injuries", name="in_action").delete()
    Selector(task_id="Football_Injuries", name="in_action", type=Selector.INTEGER).save()

    injuries = Task.get("Football_Injuries").results.all()  # get all injuries
    matches = defaultdict(lambda: [])
    for match in Task.get("Football_Matches").results.all():
        matches[match.player_id].append(match)
    for injury in injuries:
        injury.in_action = 0
        for match in matches[injury.player_id]:
            if match.date <= injury.begin <= match.date + datetime.timedelta(days=1) and match.minutes_played:
                injury.in_action = 1
                break
        injury.save()

    return HttpResponse("finished")


def injuries_synonymes(request):
    Selector.objects.filter(task_id="Football_Injuries", name="preceding_injury_date").delete()
    Selector.objects.filter(task_id="Football_Injuries", name="following_injury_date").delete()
    Selector.objects.filter(task_id="Football_Injuries", name="end_date_estimated").delete()
    Selector.objects.filter(task_id="Football_Injuries", name="preceding_injury_in_last_year").delete()
    Selector(task_id="Football_Injuries", name="preceding_injury_date", type=Selector.DATETIME).save()
    Selector(task_id="Football_Injuries", name="following_injury_date", type=Selector.DATETIME).save()
    Selector(task_id="Football_Injuries", name="end_date_estimated", type=Selector.INTEGER).save()
    Selector(task_id="Football_Injuries", name="preceding_injury_in_last_year", type=Selector.INTEGER).save()

    synonymes = """
    Außenbandanriss
    Außenbandriss
    Außenbandprobleme

    Außenbandriss Knie
    Außenbandanriss Knie

    Außenbandanriss Sprunggelenk
    Außenbandriss Sprunggelenk

    Bänderanriss
    Bänderriss
    Bänderdehnung
    Bänderverletzung

    Bänderanriss Knie
    Bänderriss Knie

    Bänderanriss Sprunggelenk
    Bänderriss Sprunggelenk
    Bänderriss in der Fußwurzel

    Innenbandabriss
    Innenbandanriss
    Innenbandriss
    Innenbandverletzung
    Innenbandzerrung

    Innenbandanriss Knie
    Innenbanddehnung Knie
    Innenbandriss Knie

    Innenbandanriss Sprunggelenk
    Innenbandriss Sprunggelenk

    Kreuzbandanriss
    Kreuzbanddehnung
    Kreuzbandriss
    Kreuzbandzerrung

    Seitenbandanriss Knie
    Seitenbandriss Knie


    Seitenbandanriss Sprunggelenk
    Seitenbandriss Sprunggelenk

    Seitenbandriss
    Seitenband-Verletzung

    Syndesmosebandanriss
    Syndesmosebandriss


    Außenmeniskuseinriss
    Meniskuseinriss
    Meniskusreizung
    Meniskusriss
    Meniskusschaden
    Meniskusverletzung

    Kapselriss
    Kapselverletzung

    Adduktorenabriss
    Adduktorenbeschwerden
    Adduktorenverletzung

    Leistenprobleme
    Leistenverletzung
    Leistenzerrung

    Muskelbündelriss
    Muskelermüdung
    Muskelfasereinriss
    Muskelfaserriss
    Muskelquetschung
    Muskelriss
    Muskelteilabriss
    Muskelverhärtung
    Muskelverletzung
    Muskelzerrung
    muskuläre Probleme

    Oberschenkelmuskelriss
    Oberschenkelprobleme
    Oberschenkelverletzung
    Oberschenkelzerrung

    Wadenmuskelriss
    Wadenzerrung

    Achillessehnenanriss
    Achillessehnenprobleme
    Achillesversenprobleme
    Achillessehnenreizung
    Achillessehnenriss

    Sehnenanriss
    Sehnenentzündung
    Sehnenreizung
    Sehnenriss

    Patellarsehnenanriss
    Patellarsehnenprobleme
    Patellarsehnenreizung
    Patellarsehnenriss
    """.split("\n")

    # Group synonyme injury descriptions #
    grouped_injuries = dict()
    group = 0
    for description in synonymes:
        description = description.strip().lower()
        if not description:
            group += 1
        else:
            grouped_injuries[description] = group

    # caluclate preceding and following injury date columns #
    injuries_by_player = defaultdict(lambda: [])
    for injury in sorted(Task.get("Football_Injuries").results.all(), key=lambda i: i.begin):  # get all injuries sorted by begin
        injury.following_injury_date = None
        injury.preceding_injury_date = None
        injury.end_date_estimated = int(not injury.end or injury.end >= datetime.datetime.now())
        injury.preceding_injury_in_last_year = 0  # := False
        injuries_by_player[injury.player_id].append(injury)

    for player_id, injuries in injuries_by_player.items():
        for i, injury1 in enumerate(injuries):
            for injury2 in injuries[i+1:]:
                if grouped_injuries.get(injury1.description.strip().lower(), injury1.description.strip().lower()) == \
                   grouped_injuries.get(injury2.description.strip().lower(), injury2.description.strip().lower()):
                    # first following similar injury found #
                    injury1.following_injury_date = injury2.begin
                    injury2.preceding_injury_date = injury1.begin
                    injury2.preceding_injury_in_last_year = int((injury2.begin - injury2.preceding_injury_date).days < 365)
                    break
            injury1.save()

    return HttpResponse("finished")


def injuries_per_day(request):
    return repr([dict(id=injury.player_id, begin=injury.begin, end=injury.end) for injury in Task.get("Fussball_Verletzungen").results.all() if injury.begin])


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
    return HttpResponse(task.export_to_excel(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


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
        return HttpResponse(json.dumps({"results": repr(eval(request.POST["command"]))}), content_type="application/json")
    except Exception as e:
        return HttpResponse(json.dumps(dict(results=str(e))), content_type="application/json")
