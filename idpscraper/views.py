""" This file contains webscraper specific views """
from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from idpscraper.models import Task, Selector, UrlSelector, Result, serialize
import json
import traceback


def index(request):
    """ Basic view listing all existing tasks """
    return render(request, 'idpscraper/index.html', dict(tasks=Task.objects.all()))


def task(request, name):
    """ Task Details / Creation assistent """
    task = Task.get(name)
    data = task.as_table(task.results.all()[:50])
    all_tasks = Task.objects.all()
    return render(request, 'idpscraper/task.html', dict(task=task, data=data, all_tasks=all_tasks, selector_choices=Selector.TYPE_CHOICES))


def console(request):
    """ Developer Console for executing pyton code during runtime. Beware: Potential Security Risk """
    return render(request, 'idpscraper/console.html')


def test_task(request, name):
    """ Fetch the first url's data of a task without persisting the data in the database """
    try:
        task = Task.get(name)
        results = task.test()[:100]
        results = "<br>".join((" ".join(str(cell) for cell in row) for row in task.as_table(results)))
        return HttpResponse(json.dumps(dict(results=results)), content_type="application/json")
    except Exception as e:
        traceback.print_exc()
        return HttpResponse(json.dumps(dict(results=str(e))), content_type="application/json")


def run_task(request, name):
    """ Execute a task and store resulting data in the database """
    try:
        Task.get(name).run()
        return HttpResponse(json.dumps(dict()), content_type="application/json")
    except Exception as e:
        traceback.print_exc()
        return HttpResponse(json.dumps(dict(results=str(e))), content_type="application/json")


def delete_results(request, name):
    """ Delete the all result data of a task """
    task = Task.get(name)
    Result.objects.filter(task=task).delete()
    return HttpResponse(json.dumps(dict()), content_type="application/json")


def export_excel(request, name):
    """ Export a task's results data to excel 2013 """
    task = Task.get(name)
    return HttpResponse(task.export_to_excel(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def export_task(request, name):
    """ Export a task specification to python """
    task = Task.get(name)
    return HttpResponse(task.export(), content_type="text/plain")


def delete_task(request, name):
    """ Delete a task """
    Task.get(name).delete()
    return HttpResponse(json.dumps(dict()), content_type="application/json")


def new_task(request):
    """ Create a new task """
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
    """ Return all selectors of a task """
    task = Task.get(name)
    selectors = list(task.selectors.all())
    return HttpResponse(json.dumps(selectors, default=serialize.serialize), content_type="application/json")


def run_command(request):
    """ Execute a command from the developer console """
    try:
        return HttpResponse(json.dumps({"results": repr(eval(request.POST["command"]))}), content_type="application/json")
    except Exception as e:
        return HttpResponse(json.dumps(dict(results=str(e))), content_type="application/json")
