from datetime import datetime  # date / time support
import logging  # support for logging to console (debuggin)
import itertools  # helpers for iterable objects
from gluon.storage import Storage  # Support for dictionary container Storage
from Scraper import Scraper, Selector  # Own Web-Scraper
from util import *  # for generic helpers
from google.appengine.api import taskqueue, memcache  # Support for scheduled, cronjob-like tasks and memcache
from google.appengine.ext import ndb  # Database support
patch_ndb()


class Result(ndb.Expando):
    """ Holds results of webscraping executions """
    results_key = ndb.KeyProperty(kind="Task", required=True)

    def __init__(self, *args, **kwds):
        super(Result, self).__init__(*args, **kwds)

    @staticmethod
    def fetch(results_key, limit=None):
        return Result.query(Result.results_key == results_key).fetch(limit=limit)

    @staticmethod
    def delete(results_key):
        ndb.delete_multi(Result.query(Result.results_key == results_key).fetch(keys_only=True))


class UrlSelector(ndb.Model):
    """ Urls that should be crawled in this task. Can be fetched from the result of other tasks """

    url_raw = ndb.StringProperty(required=True, default="")
    results_key = ndb.KeyProperty(kind="Task", required=True)
    results_property = ndb.StringProperty(required=True, default="")
    start_parameter = ndb.StringProperty(required=True, default="")

    def get_urls(self, results=None):
        """ Retrieves the urls of an URL Selector (based a result table if the url is dynamic) """
        if self.has_dynamic_url:

            if self.start_parameter:
                yield self.url_raw % self.start_parameter

            results = Result.fetch(self.results_key) if results is None else results
            for result in results:
                if getattr(result, self.results_property) is not None:
                    yield self.url_raw % getattr(result, self.results_property)

        else:
            yield self.url_raw

    @property
    def has_dynamic_url(self):
        return "%s" in self.url_raw


class Task(ndb.Model):
    """ A Webscraper Task """

    # self.key.id() := name of the tasks
    results_key = ndb.KeyProperty(kind="Task", required=True)  # name for the result. Defaults to task_name but can also refer to other task_names for appending to external results
    period = ndb.IntegerProperty(required=True, default=0)  # seconds between scheduled runs [if set]
    creation_datetime = ndb.DateTimeProperty(required=True, auto_now_add=True)
    url_selectors = ndb.StructuredProperty(UrlSelector, repeated=True)  # Urls that should be crawled in this task. Can be fetched from the result of other tasks
    selectors = ndb.StructuredProperty(Selector, repeated=True)  # Selector of webpage content

    QUEUE = taskqueue.Queue(name="task")

    @property
    def name(self):
        return str(self.key.id())

    @property
    def status(self):
        return memcache.get("status_" + self.name) or ""

    @status.setter
    def status(self, value):
        if value:
            memcache.set("status_" + self.name, value)
            logging.warning(value)
        else:
            memcache.delete("status_" + self.name)

    @property
    def key_selectors(self):
        return [selector for selector in self.selectors if selector.is_key]

    @property
    def is_recursive(self):
        return any([url_selector.has_dynamic_url and url_selector.results_key == self.results_key for url_selector in self.url_selectors])

    def __init__(self, *args, **kwds):
        kwds.setdefault("key", ndb.Key(Task, kwds.pop("name", None)))
        if kwds.get("key").id():
            ## Holds only on new creations, not on datastore retrievals ##
            kwds.setdefault("results_key", kwds.get("key"))
            kwds.setdefault("selectors", [Selector(is_key=True)])
            kwds.setdefault("url_selectors", [UrlSelector(results_key=self.key)])
        super(Task, self).__init__(*args, **kwds)

    def get_urls(self, results=None):
        return itertools.chain(*[url_selector.get_urls(results) for url_selector in self.url_selectors])  # Keep generators intact!

    @staticmethod
    def get(name):
        return ndb.Key(Task, name).get()

    def get_result_key(self, result_value_dict):
        result_id = u"".join([unicode(result_value_dict[selector.name]) for selector in self.key_selectors])
        return ndb.Key(Task, self.name, Result, None or result_id)

    def delete(self):
        self.unschedule()
        self.delete_results()
        self.key.delete()

    def delete_results(self):
        Result.delete(self.results_key)

    def get_results(self, as_table=False, limit=1000):
        results = Result.fetch(self.results_key, limit=limit)

        if not as_table:
            return results
        else:
            ## Create data table ##
            data = [tuple(selector.name for selector in self.selectors)]  # titles

            for result in results:
                data += [tuple(getattr(result, selector.name) for selector in self.selectors)]

            return data

    def unschedule(self):
        pass

    def schedule(self, store=True, test=False):
        ## TODO: do it in taskqueue and retry url errors ##
        visited_urls = zipset()
        urls = self.get_urls()

        for url in urls:
            if url in visited_urls: continue
            visited_urls.add(url)

            ## Log status ##
            self.status = "Progress: %s" % len(visited_urls)

            ## Fetch Result ##
            partial_results = [Result(key=self.get_result_key(value_dict), results_key=self.results_key, **value_dict) for value_dict in Scraper.http_request(url, selectors=self.selectors)]

            ## Only query one url in testing mode ##
            if test:
                break

            ## Append new urls on recursive call ##
            if self.is_recursive:
                urls = itertools.chain(urls, self.get_urls(partial_results))

            ## Store result in database ##
            if store:
                ndb.put_multi(partial_results)

        self.status = None

        return partial_results

    @staticmethod
    def example_tasks():
        return [
            ##### Leichtathletik #####
            Task(
                name="Leichtathletik_Sprint_100m_Herren",
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior", results_key=ndb.Key(Task, "Leichtathletik_Sprint_100m_Herren"))],
                selectors=[
                    Selector(name="athlete_id",         xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]""" + "/td[4]/a/@href", type=int, is_key=True),
                    Selector(name="first_name",         xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]""" + "/td[4]/a/text()", type=unicode),
                    Selector(name="last_name",          xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]""" + "/td[4]/a/span/text()", type=unicode),
                    Selector(name="result_time",        xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]""" + "/td[2]/text()", type=float),
                    Selector(name="competition_date",   xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]""" + "/td[9]/text()", type=datetime),
                ],
            ),
            Task(
                name="Leichtathletik_Athleten_Historie",
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/athletes/athlete=%s", results_key=ndb.Key(Task, "Leichtathletik_Sprint_100m_Herren"), results_property="athlete_id")],
                selectors=[
                    Selector(name="athlete_id", xpath="""//meta[@property = "og:url"]/@content""", type=int, is_key=True),
                    Selector(name="name", xpath="""//div[@class = "name-container athProfile"]/h1/text()""", type=unicode),
                    Selector(name="birthday", xpath="""//div[@class = "country-date-container"]//span[4]//text()""", type=datetime),
                    Selector(name="country", xpath="""//div[@class = "country-date-container"]//span[2]//text()""", type=unicode),
                ],
            ),

            ##### ImmoScout #####
            Task(
                name="Wohnungen",
                url_selectors=[
                    UrlSelector(url_raw="http://www.immobilienscout24.de%s", start_parameter="/Suche/S-T/Wohnung-Miete/Bayern/Muenchen", results_key=ndb.Key(Task, "Wohnungen"), results_property="naechste_seite"),
                    UrlSelector(url_raw="http://www.immobilienscout24.de%s", start_parameter="/Suche/S-T/Wohnung-Miete/Berlin/Berlin", results_key=ndb.Key(Task, "Wohnungen"), results_property="naechste_seite"),
                ],
                selectors=[
                    Selector(name="wohnungs_id", xpath="""//span[@class="title"]//a/@href""", type=int, is_key=True),
                    Selector(name="naechste_seite", xpath="""//span[@class="nextPageText"]/..//@href"""),
                ],
            ),
            Task(
                name="Wohnungsdetails",
                url_selectors=[UrlSelector(url_raw="http://www.immobilienscout24.de/expose/%s", results_key=ndb.Key(Task, "Wohnungen"), results_property="wohnungs_id")],
                selectors=[
                    Selector(name="wohnungs_id", xpath="""//a[@id="is24-ex-remember-link"]/@href""", type=int, is_key=True),
                    Selector(name="postleitzahl", xpath="""//div[@data-qa="is24-expose-address"]//text()""", type=int, regex="\d{5}"),
                    Selector(name="zimmeranzahl", xpath="""//dd[@class="is24qa-zimmer"]//text()""", type=int),
                    Selector(name="wohnflaeche", xpath="""//dd[@class="is24qa-wohnflaeche-ca"]//text()""", type=int),
                    Selector(name="kaltmiete", xpath="""//dd[@class="is24qa-kaltmiete"]//text()""", type=int),
                ],
            ),
        ]