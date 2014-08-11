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
    def fetch(results_key, limit=None, keys_only=False, projection=None):
        return Result.query(ancestor=results_key).fetch(limit=limit, keys_only=keys_only, projection=projection)

    @staticmethod
    def delete(results_key):
        ndb.delete_multi(Result.fetch(results_key, keys_only=True))

class UrlSelector(ndb.Model):
    """ Urls that should be crawled in this task. Can be fetched from the result of other tasks """

    url_raw = ndb.StringProperty(default="")
    results_key = ndb.KeyProperty(kind="Task", required=True)
    results_property = ndb.StringProperty(default="")
    start_parameter = ndb.StringProperty(default="")

    @property
    def selector(self):
        return self.results_key.get().get_selector(self.results_property)

    def get_urls(self, results=None, limit=None):
        """ Retrieves the urls of an URL Selector (based a result table if the url is dynamic) """
        if self.has_dynamic_url:

            if self.start_parameter:
                yield self.url_raw % self.start_parameter


            for url_parameter in self.get_url_parameters(results=results, limit=limit):
                yield self.url_raw % url_parameter

        else:
            yield self.url_raw

    def get_url_parameters(self, results=None, limit=None):
        if self.selector.is_key:
            ## only fetch keys ##
            for result_key in results or Result.fetch(self.results_key, keys_only=True, limit=limit):
                yield result_key.id()
        else:
            for result in results or Result.fetch(self.results_key, projection=[ndb.GenericProperty(self.results_property)], limit=limit):
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
        return str(self.key.id())

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

    def get_selector(self, name):
        for selector in self.selectors:
            if selector.name == name:
                return selector

    def get_urls(self, results=None, limit=None):
        return itertools.chain(*[url_selector.get_urls(results, limit=limit) for url_selector in self.url_selectors])  # Keep generators intact!

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

    def get_results(self, as_table=False, limit=100):
        results = Result.fetch(self.results_key, limit=limit)

        if not as_table:
            return results
        else:
            ## Create data table ##
            data = [[selector.name for selector in self.selectors]]  # titles

            for result in results:
                data += [[getattr(result, selector.name) for selector in self.selectors]]
            return data

    def run(self, url, store=True):
        ## Fetch Result ##
        t_ = time.clock()
        partial_results = []
        for value_dict in Scraper.http_request(url, selectors=self.selectors):
            result_key = self.get_result_key(value_dict)
            if result_key:  # Do not consider results, without key attribute
                value_dict = {selector.name: value_dict[selector.name] for selector in self.selectors}
                partial_results.append(Result(key=result_key, **value_dict))
        logging.info('Time to evaluate %s' % (time.clock() - t_))

        ## Schedule new urls on recursive call ##
        if self.is_recursive:
            self.schedule(urls=self.get_urls(partial_results))

        ## Store result in database ##
        if store:
            t_ = time.clock()
            ndb.put_multi(partial_results)
            logging.info('Time to store %s' % (time.clock() - t_))
            logging.info('Time to store per entity %s' % ((time.clock() - t_) * 1.0 / max(len(partial_results), 1)))
            logging.info("Put %s entities" % len(partial_results))
        return partial_results

    def schedule(self, urls=None):
        visited_urls = zipset()
        tasks = []

        for i, url in enumerate(urls or self.get_urls()):
            if self.is_recursive:  # Recursive tasks require a check for duplicate urls
                if url in visited_urls:
                    continue
                visited_urls.add(url)

            tasks.append(taskqueue.Task(url="/webscraper/taskqueue/run_task", params=dict(task_key=self.key.urlsafe(), url=url)))
            if not i % 1000:
                ## add batches of 1000 tasks ##
                taskqueue.Queue(name="task").add(tasks)
                tasks = []
        taskqueue.Queue(name="task").add(tasks)

    def test_run(self):
        return self.run(next(self.get_urls(limit=1)), store=False)

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