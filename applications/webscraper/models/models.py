from datetime import datetime  # date / time support
import time  # performance clocking support
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
    def __init__(self, *args, **kwds):
        super(Result, self).__init__(*args, **kwds)

    @staticmethod
    def fetch(results_key, query_options):
        query_options.entities, query_options.end_cursor, query_options.has_next = Result.query(ancestor=results_key).fetch_page(query_options.limit, keys_only=query_options.keys_only, start_cursor=query_options.start_cursor)
        return query_options.entities

    @staticmethod
    def delete(results_key):
        ndb.delete_multi(Result.fetch(results_key, query_options=Query_Options(keys_only=True, limit=1000)))

class UrlSelector(ndb.Model):
    """ Urls that should be crawled in this task. Can be fetched from the result of other tasks """

    url_raw = ndb.StringProperty(default="")
    results_key = ndb.KeyProperty(kind="Task", required=True)
    results_property = ndb.StringProperty(default="")
    start_parameter = ndb.StringProperty(default="")

    @property
    def selector(self):
        return self.results_key.get().get_selector(self.results_property)

    def get_urls(self, query_options):
        """ Retrieves the urls of an URL Selector (based a result table if the url is dynamic) """
        if self.has_dynamic_url:

            if self.start_parameter:
                yield self.url_raw % self.start_parameter


            for url_parameter in self.get_url_parameters(query_options):
                yield self.url_raw % url_parameter

        else:
            yield self.url_raw

    def get_url_parameters(self, query_options):
        for result in query_options.entities or Result.fetch(self.results_key, query_options):
            if getattr(result, self.results_property) is not None:
                yield getattr(result, self.results_property)

    @property
    def has_dynamic_url(self):
        return "%s" in self.url_raw


class Task(ndb.Model):
    """ A Webscraper Task """

    # self.key.id() := name of the tasks
    results_key = ndb.KeyProperty(kind="Task", required=True)  # name for the result. Defaults to task_name but can also refer to other task_names for appending to external results
    period = ndb.IntegerProperty(default=0)  # seconds between scheduled runs [if set]
    creation_datetime = ndb.DateTimeProperty(required=True, auto_now_add=True)
    url_selectors = ndb.StructuredProperty(UrlSelector, repeated=True)  # Urls that should be crawled in this task. Can be fetched from the result of other tasks
    selectors = ndb.StructuredProperty(Selector, repeated=True)  # Selector of webpage content

    QUEUE = taskqueue.Queue(name="task")

    @property
    def name(self):
        return unicode(self.key.id())

    @property
    def key_selectors(self):
        """ Returns all key selectors """
        return [selector for selector in self.selectors if selector.is_key]

    @property
    def is_recursive(self):
        """ Returns true if this task adds results on which its own urls are based """
        return any([url_selector.has_dynamic_url and url_selector.results_key == self.results_key for url_selector in self.url_selectors])

    def __init__(self, *args, **kwds):
        kwds.setdefault("key", ndb.Key(Task, kwds.pop("name", None)))
        if kwds.get("key").id():
            ## Holds only on new creations, not on datastore retrievals ##
            kwds.setdefault("results_key", kwds.get("key"))
            kwds.setdefault("selectors", [Selector(is_key=True)])
            kwds.setdefault("url_selectors", [UrlSelector(results_key=self.key)])
        super(Task, self).__init__(*args, **kwds)

    def get_selector(self, name):
        for selector in self.selectors:
            if selector.name == name:
                return selector

    def get_urls(self, query_options):
        return itertools.chain(*[url_selector.get_urls(query_options) for url_selector in self.url_selectors])  # Keep generators intact!

    @staticmethod
    def get(name):
        return ndb.Key(Task, name).get()

    def get_result_key(self, result_value_dict):
        result_id = u"".join([unicode(result_value_dict[selector.name]) for selector in self.key_selectors])  # Assemble Result_key from key selectors
        if result_id:
            return ndb.Key(Result, result_id, parent=self.results_key)

    def delete(self):
        self.delete_results()
        self.key.delete()

    def delete_results(self):
        Result.delete(self.results_key)
        Task.QUEUE.purge()

    def get_results(self, query_options):
        return Result.fetch(self.results_key, query_options)

    @ndb.transactional(xg=True)
    def schedule(self, query_options):
        logging.info("EXECUTING Schedule %s %s" % (self.name, query_options.start_cursor.urlsafe() if query_options.start_cursor else None))

        query_options.limit = 4  # we can only handle 5 transactional tasks per schedule
        urls = list(query_options.entities or self.get_urls(query_options))
        tasks = [taskqueue.Task(url="/webscraper/taskqueue/run_task", params=dict(task_key=self.key.urlsafe(), url=url)) for url in urls]

        ## Schedule one task per url ##
        logging.info("SCHEDULING %s Tasks for running" % len(urls))
        Task.QUEUE.add(tasks, transactional=True)

        ## Schedule next batch where last batch ended ##
        if len(urls) == query_options.limit and query_options.end_cursor and query_options.has_next:
            logging.info("SCHEDULING Schedule %s %s" % (self.name, query_options.end_cursor.urlsafe() if query_options.end_cursor else None))
            Task.QUEUE.add(taskqueue.Task(url="/webscraper/taskqueue/schedule", params=dict(name=self.name, start_cursor=query_options.end_cursor.urlsafe())), transactional=True)

    def run(self, url, store=True):
        logging.info("RUNNING %s" % url)

        ## Fetch Result ##
        results = [Result(key=self.get_result_key(value_dict), **value_dict) for value_dict in Scraper.http_request(url, selectors=self.selectors) if self.get_result_key(value_dict)]

        ## Schedule new urls on recursive call ##
        if self.is_recursive:
            self.schedule(urls=self.get_urls(Query_Options(entities=results)))

        ## Store result in database ##
        if store:
            ndb.put_multi(results)
            logging.info("PUTTING %s results" % len(results))

        return results

    def test_run(self):
        return self.run(next(self.get_urls(Query_Options(limit=1))), store=False)

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
                name="Leichtathletik_Disziplinen",
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/athletes", results_key=ndb.Key(Task, "Leichtathletik_Disziplinen"))],
                selectors=[
                    Selector(name="disciplin", xpath="""//select[@id="selectDiscipline"]/option/@value""", type=str, is_key=True),
                ],
            ),
            Task(
                name="Leichtathletik_Athleten",
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/athletes/search?name=&country=&discipline=%s&gender=", results_key=ndb.Key(Task, "Leichtathletik_Disziplinen"), results_property="disciplin")],
                selectors=[
                    Selector(name="athlete_id", xpath="""//table[@class="records-table"]//tr[not(@class)]/td[1]//@href""", type=int, is_key=True),
                    Selector(name="first_name", xpath="""//table[@class="records-table"]//tr[not(@class)]/td[1]//a/text()""", type=unicode),
                    Selector(name="last_name", xpath="""//table[@class="records-table"]//tr[not(@class)]/td[1]/a/span/text()""", type=unicode),
                    Selector(name="sex", xpath="""//table[@class="records-table"]//tr[not(@class)]/td[2]/text()""", type=unicode),
                    Selector(name="country", xpath="""//table[@class="records-table"]//tr[not(@class)]/td[3]/text()""", type=unicode),
                    Selector(name="birthday", xpath="""//table[@class="records-table"]//tr[not(@class)]/td[4]/text()""", type=datetime),
                ],
            ),
            Task(
                name="Leichtathletik_Performance",
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/athletes/athlete=%s", results_key=ndb.Key(Task, "Leichtathletik_Athleten"), results_property="athlete_id")],
                selectors=[
                    Selector(name="athlete_id", xpath="""//meta[@name="url"]/@content""", type=int),
                    Selector(name="performance", xpath="""//div[@id="panel-progression"]//tr[count(td)>3]//td[2]""", type=float),
                    Selector(name="datetime", xpath="""merge_lists(//div[@id="panel-progression"]//tr[count(td)>3]/td[last()], //div[@id="panel-progression"]//tr[count(td)>3]/td[1])""", type=datetime),
                    Selector(name="place", xpath="""//div[@id="panel-progression"]//tr[count(td)>3]//td[last()-1]""", type=unicode),
                    Selector(name="discipline", xpath="""exe(//div[@id="panel-progression"]//tr[count(td)>3]//td[2], "../preceding::tr/td[@class='sub-title']")""", type=unicode),
                    Selector(name="performance_key", xpath="""merge_lists(//div[@id="panel-progression"]//tr[count(td)>3]/td[last()], //div[@id="panel-progression"]//tr[count(td)>3]/td[1], //meta[@name="url"]/@content)""", type=unicode, is_key=True),
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