import feedparser  # autodetection of date formats
from datetime import datetime  # date / time support
import logging  # support for logging to console (debuggin)
import itertools  # helpers for iterable objects
from gluon.storage import Storage  # Support for dictionary container Storage
from Scraper import Scraper  # Own Web-Scraper
from util import *  # for generic helpers

## google app engine ##
from google.appengine.ext import ndb  # Database support
patch_ndb()
from google.appengine.api import taskqueue, memcache  # Support for scheduled, cronjob-like tasks and memcache


class Result(ndb.Expando):
    """ Holds results of webscraping executions """
    results_key = ndb.KeyProperty(kind="Task", required=True)

    def __init__(self, *args, **kwds):
        super(Result, self).__init__(*args, **kwds)

    @staticmethod
    def fetch(results_key):
        return Result.query(Result.results_key == results_key).fetch()

    @staticmethod
    def delete(results_key):
        ndb.delete_multi(Result.query(Result.results_key == results_key).fetch(keys_only=True))


class Selector(ndb.Model):
    """ Contains information for selecting a ressource on a xml/html page """
    TYPES = [str, unicode, int, float, datetime]

    is_key = ndb.BooleanProperty(required=True, default=False)  # if given: All selectors with is_key=True are combined to the key for a result row
    name = ndb.StringProperty(required=True, default="")
    xpath = ndb.StringProperty(required=True, default="")
    def type_setter(prop, self, value):
        if issubclass(value, unicode):
            self.regex = self.regex or r"[^\n\r ,.][^\n\r]+"
        elif issubclass(value, int):
            self.regex = self.regex or r"\d[\d.,]+"
        elif issubclass(value, float):
            self.regex = self.regex or r"\d[\d.,]+"
        elif issubclass(value, datetime):
            self.regex = self.regex or r"\d+ \w+ \d+"
        return value
    type = ndb.PickleProperty(required=True, default=str, setters=[type_setter])
    def regex_setter(prop, self, value):
        if not value:
            return self.regex  # Do not overwrite the regex that is forced by the type
        return value
    regex = ndb.StringProperty(required=True, default="", setters=[regex_setter])

    @property
    def output_cast(self):
        if issubclass(self.type, unicode):
            return unicode
        elif issubclass(self.type, int):
            return lambda s: int(str2float(s))
        elif issubclass(self.type, float):
            return str2float
        elif issubclass(self.type, datetime):
            return lambda data: datetime(*(feedparser._parse_date(data)[:6]))
        elif issubclass(self.type, str):
            return lambda data: data

class UrlSelector(ndb.Model):
    """ Urls that should be crawled in this task. Can be fetched from the result of other tasks """

    url_raw = ndb.StringProperty(required=True, default="")
    results_key = ndb.KeyProperty(kind="Task", required=True)
    results_property = ndb.StringProperty(required=True, default="")
    start_parameter = ndb.StringProperty(required=True, default="")

    @property
    def urls(self):
        if "%s" in self.url_raw:  # The url must be generated
            results = Result.fetch(self.results_key)
            return {self.url_raw % self.start_parameter} | set(self.url_raw % getattr(result, self.results_property) for result in results if getattr(result, self.results_property) is not None)  # Convert result into a set to remove duplicates
        else:
            return [self.url_raw]


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

    @property
    def key_selectors(self):
        return [selector for selector in self.selectors if selector.is_key]

    def __init__(self, *args, **kwds):
        kwds.setdefault("key", ndb.Key(Task, kwds.pop("name", None)))
        if kwds.get("key").id():
            ## Holds only on new creations, not on datastore retrievals ##
            kwds.setdefault("results_key", kwds.get("key"))
            kwds.setdefault("selectors", [Selector(is_key=True)])
            kwds.setdefault("url_selectors", [UrlSelector(results_key=self.key)])
        super(Task, self).__init__(*args, **kwds)

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

    def get_results(self, as_table=False):
        results = Result.fetch(self.results_key)

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
        results = []
        visited_urls = set()
        remaining_urls = self.urls

        while remaining_urls:  # and len(visited_urls) < 10:  # urls may change during iteration. Therefore for-each is not applicable.
            url = remaining_urls.pop()

            ## Fetch Result ##
            partial_results = [Result(key=self.get_result_key(value_dict), results_key=self.results_key, **value_dict) for value_dict in Scraper.http_request(url, selectors=self.selectors)]
            results += partial_results

            ## Only query one url in testing mode ##
            if test:
                break

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