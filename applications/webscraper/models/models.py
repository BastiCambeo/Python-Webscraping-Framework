import feedparser  # autodetection of date formats
from datetime import datetime  # date / time support
import logging  # support for logging to console (debuggin)
import itertools  # helpers for iterable objects
from gluon.storage import Storage  # Support for dictionary container Storage
from Scraper import Scraper  # Own Web-Scraper
from util import *  # for generic helpers

## google app engine ##
from google.appengine.ext import ndb  # Database support
from google.appengine.api import taskqueue, memcache  # Support for scheduled, cronjob-like tasks and memcache


class Result(ndb.Expando):
    """ Holds results of webscraping executions """
    result_name = ndb.StringProperty(required=True)

    @staticmethod
    def fetch(result_name):
        return Result.query(Result.result_name == result_name).fetch()

    @staticmethod
    def delete(result_name):
        ndb.delete_multi(Result.query(Result.result_name == result_name).fetch(keys_only=True))

    @staticmethod
    def get_result_key(self, task):
        key_name = ""

        for selector in task.selectors:
            if selector.is_key:
                key_name += str(getattr(self, selector.name))

        return ndb.Key(Task, task.key.id(), Result, None or key_name)


class Selector(ndb.Model):
    """ Contains information for selecting a ressource on a xml/html page """

    is_key = ndb.BooleanProperty(required=True, default=False)  # if given: All selectors with is_key=True are combined to the key for a result row
    name = ndb.StringProperty(required=True)
    xpath = ndb.StringProperty(required=True)
    type = ndb.PickleProperty()
    regex = ndb.StringProperty()

    @property
    def output_cast(self):
        if issubclass(self.type, basestring):
            return unicode
        elif issubclass(self.type, int):
            return lambda s: int(str2float(s))
        elif issubclass(self.type, float):
            return str2float
        elif issubclass(self.type, datetime):
            return lambda data: datetime(*(feedparser._parse_date(data)[:6]))
        else:
            return lambda data: data

    def __init__(self, *args, **kwds):
        if "type" in kwds:
            if issubclass(kwds["type"], basestring):
                kwds.setdefault("regex", "\w[\w\s]*\w|\w")
            elif issubclass(kwds["type"], int):
                kwds.setdefault("regex", "\d[\d.,]+")
            elif issubclass(kwds["type"], float):
                kwds.setdefault("regex", "\d[\d.,]+")
            elif issubclass(kwds["type"], datetime):
                kwds.setdefault("regex", "\d+ \w+ \d+")
        super(Selector, self).__init__(*args, **kwds)


class UrlSelector(ndb.Model):
    """ Urls that should be crawled in this task. Can be fetched from the result of other tasks """

    url_raw = ndb.StringProperty(required=True)
    result_name = ndb.StringProperty()
    prop = ndb.StringProperty()
    start_parameter = ndb.StringProperty()

    @property
    def urls(self):
        if "%s" in self.url_raw:  # The url must be generated
            entities = Result.fetch(self.result_name)
            return {self.url_raw % self.start_parameter} | set(self.url_raw % getattr(entity, self.prop) for entity in entities)  # Convert result into a set to remove duplicates
        else:
            return [self.url_raw]


class Task(ndb.Model):
    """ A Webscraper Task """

    # self.key.id() := name of the tasks
    result_name = ndb.StringProperty(required=True)  # name for the result. Defaults to task_name but can also refer to other task_names for appending to external results
    period = ndb.IntegerProperty()  # seconds between scheduled runs [if set]
    creation_datetime = ndb.DateTimeProperty(auto_now_add=True)
    url_selectors = ndb.StructuredProperty(UrlSelector, repeated=True)  # Urls that should be crawled in this task. Can be fetched from the result of other tasks
    selectors = ndb.StructuredProperty(Selector, repeated=True)  # Selector of webpage content

    QUEUE = taskqueue.Queue(name="task")

    @property
    def name(self):
        return str(self.key.id())

    @property
    def urls(self):
        return set(itertools.chain(*[url_selector.urls for url_selector in self.url_selectors]))

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

    def __init__(self, *args, **kwds):
        kwds.setdefault("key", ndb.Key(Task, kwds.pop("name", None)))
        kwds.setdefault("result_name", kwds.get("key").id())
        super(Task, self).__init__(*args, **kwds)

    @staticmethod
    def get(name):
        return ndb.Key(Task, name).get()

    def delete(self):
        self.unschedule()
        self.delete_results()
        self.key.delete()

    def delete_results(self):
        Result.delete(self.result_name)

    def get_results(self, as_table=False):
        results = Result.fetch(self.result_name)

        if not as_table:
            return results
        else:
            ## Create data table ##
            data = [tuple(selector.name for selector in self.selectors)]  # titles

            for result in results:
                data += [tuple(getattr(result, selector.name) for selector in self.selectors)]

            return data

    def unschedule(self):
        raise NotImplementedError

    def schedule(self, store=True):
        results = []
        visited_urls = set()
        remaining_urls = self.urls

        while remaining_urls:  # and len(visited_urls) < 10:  # urls may change during iteration. Therefore for-each is not applicable.
            url = remaining_urls.pop()

            ## Fetch Result ##
            partial_results = [Result(key=Result.get_result_key(value_dict, self), result_name=self.result_name, **value_dict) for value_dict in Scraper.http_request(url, selectors=self.selectors)]
            results += partial_results

            ## Store result in database ##
            if store:
                ndb.put_multi(partial_results)

            ## Update urls ##
            visited_urls |= {url}
            remaining_urls = self.urls - visited_urls  # Need to be evaluated after new results have committed (For recursive Crawler)

            ## Log status ##
            self.status = "Progress: %s/%s" % (len(visited_urls), len(remaining_urls)+len(visited_urls)) if remaining_urls else None

        return results

    @staticmethod
    def example_tasks():
        return [
            ##### Leichtathletik #####
            Task(
                name="Leichthatletik_Sprint_100m_Herren",
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior")],
                selectors=[
                    Selector(name="athlete_id",         xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]""" + "/td[4]/a/@href", type=int, is_key=True),
                    Selector(name="first_name",         xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]""" + "/td[4]/a/text()", type=unicode),
                    Selector(name="last_name",          xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]""" + "/td[4]/a/span/text()", type=unicode),
                    Selector(name="result_time",        xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]""" + "/td[2]/text()", type=float),
                    Selector(name="competition_date",   xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]""" + "/td[9]/text()", type=datetime),
                ],
            ),
            Task(
                name="Leichthatletik_Athleten",
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/athletes/athlete=%s", result_name="Leichthatletik_Sprint_100m_Herren", prop="athlete_id")],
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
                    UrlSelector(url_raw="http://www.immobilienscout24.de%s", start_parameter="/Suche/S-T/Wohnung-Miete/Bayern/Muenchen", result_name="Wohnungen", prop="naechste_seite"),
                    UrlSelector(url_raw="http://www.immobilienscout24.de%s", start_parameter="/Suche/S-T/Wohnung-Miete/Berlin/Berlin", result_name="Wohnungen", prop="naechste_seite"),
                ],
                selectors=[
                    Selector(name="wohnungs_id", xpath="""//span[@class="title"]//a/@href""", type=int, is_key=True),
                    Selector(name="naechste_seite", xpath="""//span[@class="nextPageText"]/..//@href"""),
                ],
            ),
            Task(
                name="Wohnungsdetails",
                url_selectors=[UrlSelector(url_raw="http://www.immobilienscout24.de/expose/%s", result_name="Wohnungen", prop="wohnungs_id")],
                selectors=[
                    Selector(name="wohnungs_id", xpath="""//a[@id="is24-ex-remember-link"]/@href""", type=int, is_key=True),
                    Selector(name="postleitzahl", xpath="""//div[@data-qa="is24-expose-address"]//text()""", type=int, regex="\d{5}"),
                    Selector(name="zimmeranzahl", xpath="""//dd[@class="is24qa-zimmer"]//text()""", type=int),
                    Selector(name="wohnflaeche", xpath="""//dd[@class="is24qa-wohnflaeche-ca"]//text()""", type=int),
                    Selector(name="kaltmiete", xpath="""//dd[@class="is24qa-kaltmiete"]//text()""", type=int),
                ],
            ),
        ]