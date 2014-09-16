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
    @staticmethod
    def fetch(results_key, query_options):
        return Result.query(ancestor=results_key).fetch(query_options.limit, keys_only=query_options.keys_only)

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
        return uni(self.key.id())

    @property
    def key_selectors(self):
        """ Returns all key selectors """
        return [selector for selector in self.selectors if selector.is_key]

    @property
    def recursive_url_selectors(self):
        return filter(lambda url_selector: url_selector.has_dynamic_url and url_selector.results_key == self.results_key, self.url_selectors)

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

    def get_urls(self, query_options=Query_Options()):
        return itertools.chain(*[url_selector.get_urls(query_options) for url_selector in self.url_selectors])  # Keep generators intact!

    @staticmethod
    def get(name):
        return ndb.Key(Task, name).get()

    def get_result_key(self, result_value_dict):
        result_id = u"".join([unicode(result_value_dict[selector.name]) for selector in self.key_selectors if result_value_dict[selector.name]])  # Assemble Result_key from key selectors
        if result_id:
            return ndb.Key(Result, result_id, parent=self.results_key)

    def delete(self):
        self.delete_results()
        self.key.delete()

    def delete_results(self):
        Result.delete(self.results_key)
        Task.QUEUE.purge()

    def get_results(self, query_options=Query_Options()):
        return Result.fetch(self.results_key, query_options=query_options)

    def schedule(self, schedule_id=None, urls=None):
        schedule_id = schedule_id or str(int(time.time()))

        for url in urls or set(self.get_urls()):
            try:
                taskqueue.add(url="/webscraper/taskqueue/run_task", params=dict(schedule_id=schedule_id, url=url, name=self.key.id()), name=schedule_id+str(hash(url)), queue_name="task")
            except (taskqueue.DuplicateTaskNameError, taskqueue.TaskAlreadyExistsError, taskqueue.TombstonedTaskError):
                pass  # only schedule any url once per schedule

    def run(self, url, schedule_id=None, store=True):
        ## Fetch Result ##
        results = [Result(key=self.get_result_key(value_dict), **value_dict) for value_dict in Scraper.http_request(url, selectors=self.selectors) if self.get_result_key(value_dict)]

        if store:
            ## Store result in database ##
            ndb.put_multi(results)

            ## Schedule new urls on recursive call ##
            if self.recursive_url_selectors:
                self.schedule(schedule_id=schedule_id, urls=self.recursive_url_selectors[0].get_urls(Query_Options(entities=results)))

        return results

    def test(self):
        return self.run(url=next(self.get_urls(Query_Options(limit=1))) ,store=False)

    @staticmethod
    def example_tasks():
        return [
            ##### Fußball #####
            Task(
                name="Fussball_Saisons",
                url_selectors=[UrlSelector(url_raw="http://www.transfermarkt.de/3262/kader/verein/3262/", results_key=ndb.Key(Task, "Fussball_Saisons"))],
                selectors=[
                    Selector(name="saison",         xpath="""//select[@name="saison_id"]/option/@value""", type=unicode, is_key=True),
                ],
            ),
            Task(
                name="Fussball_Spieler",
                url_selectors=[UrlSelector(url_raw="http://www.transfermarkt.de/3262/kader/verein/3262/plus/1/saison_id/%s", results_key=ndb.Key(Task, "Fussball_Saisons"), results_property="saison")],
                selectors=[
                    Selector(name="spieler_id",     xpath="""//a[@class="spielprofil_tooltip"]/@href""", type=int, is_key=True),
                ],
            ),
            Task(
                name="Fussball_Spieler_Details",
                url_selectors=[UrlSelector(url_raw="http://www.transfermarkt.de/daten/profil/spieler/%s", results_key=ndb.Key(Task, "Fussball_Spieler"), results_property="spieler_id")],
                selectors=[
                    Selector(name="spieler_id",     xpath="""//link[@rel="canonical"]/@href""", type=int, is_key=True),
                    Selector(name="name",     xpath="""//div[@class="spielername-profil"]/text()"]""", type=unicode),
                    Selector(name="position",     xpath="""//table[@class="profilheader"]//td[preceding-sibling::th/text()="Position:"]""", type=unicode),
                    Selector(name="max_value",     xpath="""//table[@class="auflistung mt10"]/tr[3]/td/text()""", type=float),
                    Selector(name="birthday",     xpath="""//td[preceding-sibling::th/text()="Geburtsdatum:"]/a/text()""", type=datetime),
                    Selector(name="size",     xpath="""//td[preceding-sibling::th/text()="Größe:"]//text()""", type=float),
                ],
            ),
            Task(
                name="Fussball_Transfers",
                url_selectors=[UrlSelector(url_raw="http://www.transfermarkt.de/daten/profil/spieler/%s", results_key=ndb.Key(Task, "Fussball_Spieler"), results_property="spieler_id")],
                selectors=[
                    Selector(name="spieler_id",     xpath="""//a[@class="megamenu"][1]/@href""", type=int),
                    Selector(name="date",     xpath="""(//table)[3]//tr/td[2]//text()""", type=datetime),
                    Selector(name="from",     xpath="""(//table)[3]//tr/td[5]/a/text()""", type=unicode),
                    Selector(name="to",     xpath="""(//table)[3]//tr/td[8]/a/text()""", type=unicode),
                    Selector(name="transfer_key",     xpath="""merge_lists(//a[@class="megamenu"][1]/@href, (//table)[3]//tr/td[5]/a/text(), (//table)[3]//tr/td[8]/a/text())""", type=unicode, is_key=True),
                ],
            ),
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