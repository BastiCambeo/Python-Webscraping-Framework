#!/usr/bin/env python
import os
import sys
import webbrowser


def init_apartments():
    from idpscraper.views import Task, Selector, UrlSelector
    mods = [
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
    ]

    for m in mods:
        m.save()

if __name__ == "__main__":
    # Apply settings
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "idp.settings")

    # Test python packages
    try:
        from django.core.management import execute_from_command_line
        import picklefield
        import feedparser
        import lxml
        import requests
        import xlsxwriter
    except ImportError:
        libs = [
            "django==1.10.1",
            "django-picklefield==0.3.2",
            "feedparser==5.2.1",
            "lxml==3.6.4",
            "requests==2.11.1",
            "xlsxwriter==0.9.3"
        ]
        import subprocess
        print("Trying to install libs via pip3:")
        subprocess.run(["pip3", "install", *libs])

    # Start server if no argument was given
    if len(sys.argv) == 1:
        # Check if database and models have been initialized
        if not os.path.exists("db.sqlite3"):
            print("No database found. Creating tables now ...")
            execute_from_command_line(sys.argv + ["makemigrations"])
            execute_from_command_line(sys.argv + ["migrate"])
            init_apartments()
            print("... Finished creating tables.")
            webbrowser.open_new("http://localhost:8080/idpscraper/apartment_settings")
        sys.argv += ["runserver", "8080"]
    execute_from_command_line(sys.argv)

