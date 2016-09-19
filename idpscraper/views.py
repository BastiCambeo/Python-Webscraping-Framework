""" This file contains webscraper specific views """
from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from idpscraper.models import Task, Selector, UrlSelector, Result, ApartmentSettings, serialize
import json
import traceback
import datetime
import logging
from django.utils.timezone import utc

logging.basicConfig(level=logging.INFO)


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


def init_apartments():
    for m in [
        Task(name='immobielienscout24.de'),
        Selector(task_id='immobielienscout24.de', name='wohnungs_id', type=0, xpath='//a[@class="result-list-entry__brand-title-container"]/@data-go-to-expose-id', regex='\\d[\\d.,]*', is_key=True),
        Selector(task_id='immobielienscout24.de', name='adresse', type=1, xpath='//div[@class="result-list-entry__address nine-tenths"]//span/text()', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        Selector(task_id='immobielienscout24.de', name='kaltmiete', type=0, xpath='//div[@data-is24-qa="attributes"]//dl[1]/dd', regex='\\d[\\d.,]*', is_key=False),
        Selector(task_id='immobielienscout24.de', name='wohnflaeche', type=0, xpath='//div[@data-is24-qa="attributes"]//dl[2]/dd', regex='\\d[\\d.,]*', is_key=False),
        Selector(task_id='immobielienscout24.de', name='zimmeranzahl', type=3, xpath='//div[@data-is24-qa="attributes"]//dl[3]/dd', regex='\\d[\\d.,:]*', is_key=False),
        Selector(task_id='immobielienscout24.de', name='url', type=1, xpath='//a[@class="result-list-entry__brand-title-container"]/@href', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        Selector(task_id='immobielienscout24.de', name='base_url', type=1, xpath='//link[@rel="canonical"]/@href', regex='.*\\.de', is_key=False),
        Selector(task_id='immobielienscout24.de', name='title', type=1, xpath='//h5/text()', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        UrlSelector(task_id='immobielienscout24.de', url='http://www.immobilienscout24.de/Suche/controller/sorting.go?searchUrl=/Wohnung-Miete/Fahrzeitsuche/M_fcnchen/-/116301/2030629/-/-/30/1,50-/40,00-/EURO--900,00/-/-/-/-/-/-/-/-/-/-/-/-/true&sortingControl=2', selector_task_id='immobielienscout24.de', selector_name='wohnungs_id', selector_name2='wohnungs_id'),

        Task(name='immowelt.de'),
        Selector(task_id='immowelt.de', name='adresse', type=1, xpath='//div[contains(@class,"listitem")]//div[contains(@class,"location")]/text()', regex='[^\\n\\r ,.].+', is_key=False),
        Selector(task_id='immowelt.de', name='kaltmiete', type=0, xpath='//div[contains(@class,"listitem")]//div[@class="hardfact price_rent"]/strong/text()', regex='\\d[\\d.,]*', is_key=False),
        Selector(task_id='immowelt.de', name='wohnflaeche', type=0, xpath='//div[contains(@class,"listitem")]//div[@class="hardfact "]', regex='\\d[\\d.,]*', is_key=False),
        Selector(task_id='immowelt.de', name='wohnungs_id', type=1, xpath='//div[contains(@class,"listitem")]/a/@href', regex='/expose/([a-zA-Z0-9]+)', is_key=True),
        Selector(task_id='immowelt.de', name='zimmeranzahl', type=3, xpath='//div[contains(@class,"listitem")]//div[@class="hardfact rooms"]', regex='\\d[\\d.,:]*', is_key=False),
        Selector(task_id='immowelt.de', name='url', type=1, xpath='//div[@class="listitem relative js-listitem "]/a/@href', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        Selector(task_id='immowelt.de', name='base_url', type=1, xpath='//link[@rel="next"]/@href', regex='.*\\.de', is_key=False),
        Selector(task_id='immowelt.de', name='title', type=1, xpath='//h2', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        UrlSelector(task_id='immowelt.de', url='https://www.immowelt.de/liste/muenchen-bogenhausen/wohnungen/mieten?geoid=10809162000016%2C10809162000017%2C10809162000019%2C10809162000020%2C10809162000026%2C10809162000027%2C10809162000003%2C10809162000002%2C10809162000031%2C10809162000008%2C10809162000028&prima=1200&wflmi=30', selector_task_id='immowelt.de', selector_name='adresse',
                    selector_name2='adresse'),

        Task(name='wg-gesucht.de'),
        Selector(task_id='wg-gesucht.de', name='adresse', type=1, xpath='id("table-compact-list")//td[@class="ang_spalte_stadt row_click"]//span', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        Selector(task_id='wg-gesucht.de', name='kaltmiete', type=0, xpath='id("table-compact-list")//td[@class="position-relative ang_spalte_miete row_click"]//span/b', regex='\\d[\\d.,]*', is_key=False),
        Selector(task_id='wg-gesucht.de', name='wohnflaeche', type=0, xpath='id("table-compact-list")//td[@class="ang_spalte_groesse row_click"]//span', regex='\\d[\\d.,]*', is_key=False),
        Selector(task_id='wg-gesucht.de', name='wohnungs_id', type=1, xpath='id("table-compact-list")//td[@class="ang_spalte_groesse row_click"]/a/@href', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=True),
        Selector(task_id='wg-gesucht.de', name='zimmeranzahl', type=3, xpath='id("table-compact-list")//td[@class="ang_spalte_zimmer row_click"]//span', regex='\\d[\\d.,:]*', is_key=False),
        Selector(task_id='wg-gesucht.de', name='url', type=1, xpath='id("table-compact-list")//td[@class="ang_spalte_groesse row_click"]/a/@href', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        Selector(task_id='wg-gesucht.de', name='base_url', type=1, xpath='//link[@rel="canonical"]/@href', regex='(http://[^/]+).*', is_key=False),
        Selector(task_id='wg-gesucht.de', name='title', type=1, xpath='id("table-compact-list")//td[@class="ang_spalte_stadt row_click"]//span/text()', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        UrlSelector(task_id='wg-gesucht.de', url='http://www.wg-gesucht.de/wohnungen-in-Muenchen.90.2.0.0.html?filter=e25a980657c1a13e4d78a142aacce07e5199a55c3599e5a309', selector_task_id='wg-gesucht.de', selector_name='adresse', selector_name2='adresse'),

        # Task(name='Wohnungsdetails'),
        # Selector(task_id='Wohnungsdetails', name='wohnungs_id', type=0, xpath='//a[@id="is24-ex-remember-link"]/@href', regex='\\d[\\d.,]*', is_key=True),
        # Selector(task_id='Wohnungsdetails', name='gesamtmiete', type=3, xpath='//strong[@class="is24qa-gesamtmiete"]/text()[2]', regex='\\d[\\d.,:]*', is_key=False),
        # Selector(task_id='Wohnungsdetails', name='zimmeranzahl', type=3, xpath='//dd[@class="is24qa-zimmer"]//text()', regex='\\d[\\d.,:]*', is_key=False),
        # Selector(task_id='Wohnungsdetails', name='wohnflaeche', type=0, xpath='//dd[@class="is24qa-wohnflaeche-ca"]//text()', regex='\\d[\\d.,]*', is_key=False),
        # Selector(task_id='Wohnungsdetails', name='kaltmiete', type=0, xpath='//dd[@class="is24qa-kaltmiete"]/text()[2]', regex='\\d[\\d.,]*', is_key=False),
        # Selector(task_id='Wohnungsdetails', name='addresse', type=1, xpath='all(//div[@data-qa="is24-expose-address"]//text())', regex='(.*)Karte', is_key=False),
        # UrlSelector(task_id='Wohnungsdetails', url='http://www.immobilienscout24.de/expose/%s', selector_task_id='immobielienscout24.de', selector_name='wohnungs_id', selector_name2='wohnungs_id'),
    ]:
        m.save()


def apartment_settings(request):
    """ Apartment Settings """
    return render(request, 'idpscraper/apartment_settings.html', dict(apartment_settings=ApartmentSettings.get()))


def save_apartment_settings(request):
    """ save_apartment_settings """
    apartment_settings = ApartmentSettings.get()
    apartment_settings.email_to = request.POST.get("email_to")
    apartment_settings.email_from = request.POST.get("email_from")
    apartment_settings.password = request.POST.get("password")
    apartment_settings.smtp_server = request.POST.get("smtp_server")
    apartment_settings.smtp_port = request.POST.get("smtp_port")
    apartment_settings.fetch_intervall = request.POST.get("fetch_intervall")
    apartment_settings.save()

    return HttpResponse(json.dumps(dict()), content_type="application/json")


def run_apartment_settings(request):
    """ run_apartment_settings """
    apartment_settings = ApartmentSettings.get()
    if (datetime.datetime.utcnow().replace(tzinfo=utc) - apartment_settings.last_update).seconds > apartment_settings.fetch_intervall + 10:
        from threading import Thread
        Thread(target=apartment_worker, daemon=True).start()
        message = "Successfully started worker"
    else:
        message = "Worker already running"
    logging.info(message)
    return HttpResponse(json.dumps(dict(message=message)), content_type="application/json")


def apartment_worker():
    apartment_settings = ApartmentSettings.get()

    immoscout = Task.get("immobielienscout24.de")
    immowelt = Task.get("immowelt.de")
    wggesucht = Task.get("wg-gesucht.de")

    while True:
        apartment_settings.last_update = datetime.datetime.utcnow().replace(tzinfo=utc)
        apartment_settings.save()
        old_wohnungen = set(wohnung.wohnungs_id for wohnung in list(immoscout.results.all()) + list(immowelt.results.all()) + list(wggesucht.results.all()))
        new_wohnungen = set(wohnung.wohnungs_id for wohnung in immoscout.run() + immowelt.run() + wggesucht.run())
        new_wohnungen -= old_wohnungen
        new_wohnungen = set(wohnung for wohnung in list(immoscout.results.all()) + list(immowelt.results.all()) + list(wggesucht.results.all())
                            if wohnung.wohnungs_id in new_wohnungen and
                            wohnung.kaltmiete and wohnung.wohnflaeche and wohnung.kaltmiete / wohnung.wohnflaeche >= 12 and
                            wohnung.zimmeranzahl > 1 and
                            not getattr(wohnung, "free_until", None)
        )

        if new_wohnungen:
            import smtplib
            from email.mime.text import MIMEText

            text = "<tr><td>Titel</td><td>Kaltmiete</td><td>Fläche</td><td>Zimmer</td><td>Adresse</td></tr>"

            for wohnung in new_wohnungen:
                text += "".join(["<tr><td><a href='%s%s'>%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (wohnung.base_url, wohnung.url, wohnung.title, wohnung.kaltmiete, wohnung.wohnflaeche, wohnung.zimmeranzahl, wohnung.adresse)])

            text = "<table border>%s</table>" % text

            msg = MIMEText(text, 'html')

            msg['Subject'] = '%s Neue Wohnungen' % len(new_wohnungen)
            msg['From'] = apartment_settings.email_from
            msg['To'] = apartment_settings.email_to

            s = smtplib.SMTP_SSL(apartment_settings.smtp_server, apartment_settings.smtp_port)
            s.login(apartment_settings.email_from, apartment_settings.password)
            s.sendmail(apartment_settings.email_to, [apartment_settings.email_to], msg.as_string())
            s.quit()
            logging.info("Send Mail: " + msg['Subject'])

        import time
        time.sleep(apartment_settings.fetch_intervall)