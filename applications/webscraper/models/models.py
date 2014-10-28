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
    task_key = ndb.KeyProperty(kind="Task")


class UrlSelector(ndb.Model):
    """ Urls that should be crawled in this task. Can be fetched from the result of other tasks """

    url_raw = ndb.StringProperty(default="")
    task_key = ndb.KeyProperty(kind="Task", required=True)
    selector_name = ndb.StringProperty(default="")
    start_parameter = ndb.StringProperty(default="")

    @property
    def selector(self):
        return self.task_key.get().get_selector(self.selector_name)

    def get_urls(self, query_options=None):
        """ Retrieves the urls of an URL Selector (based a result table if the url is dynamic) """
        if self.has_dynamic_url:

            if self.start_parameter:
                yield self.url_raw % self.start_parameter


            for url_parameter in self.get_url_parameters(query_options=query_options):
                yield self.url_raw % url_parameter

        else:
            yield self.url_raw

    def get_url_parameters(self, query_options=None):
        query_options = query_options or Query_Options()
        for result in query_options.entities or self.task_key.get().get_results():
            if getattr(result, self.selector_name) is not None:
                yield getattr(result, self.selector_name)

    @property
    def has_dynamic_url(self):
        return "%s" in self.url_raw


class Task(ndb.Model):
    """ A Webscraper Task """

    # self.key.id() := name of the tasks
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
        return filter(lambda url_selector: url_selector.has_dynamic_url and url_selector.task_key == self.key, self.url_selectors)

    def __init__(self, *args, **kwds):
        kwds.setdefault("key", ndb.Key(Task, kwds.pop("name", None)))
        if kwds.get("key").id():
            ## Holds only on new creations, not on datastore retrievals ##
            kwds.setdefault("selectors", [Selector(is_key=True)])
            kwds.setdefault("url_selectors", [UrlSelector(task_key=kwds.get("key"))])
        super(Task, self).__init__(*args, **kwds)

    def get_selector(self, name):
        for selector in self.selectors:
            if selector.name == name:
                return selector

    def get_urls(self, query_options=None):
        return itertools.chain(*[url_selector.get_urls(query_options=query_options) for url_selector in self.url_selectors])  # Keep generators intact!

    @staticmethod
    def get(name):
        return ndb.Key(Task, name).get()

    def get_result_key(self, result_value_dict):
        result_id = u" ".join([unicode(result_value_dict[selector.name]) for selector in self.key_selectors if result_value_dict[selector.name]])  # Assemble Result_key from key selectors
        if result_id:
            return ndb.Key(Result, self.name + result_id)

    def delete(self):
        self.delete_results()
        self.key.delete()

    def delete_results(self):
        ndb.delete_multi(self.get_results(Query_Options(keys_only=True)))
        Task.QUEUE.purge()

    @staticmethod
    def delete_all_results(cursor=None):
        result_keys, next_curs, more = Result.query().fetch_page(1000, start_cursor=cursor, keys_only=True)
        ndb.delete_multi(result_keys)
        if more and next_curs:
            taskqueue.add(url="/webscraper/taskqueue/delete_results", params=dict(cursor=next_curs.urlsafe()))

    def get_results(self, query_options=None):
        query_options = query_options or Query_Options()
        return Result.query(Result.task_key == self.key).fetch(limit=query_options.limit, keys_only=query_options.keys_only, offset=query_options.offset)

    def get_results_as_table(self, query_options=None):
        results = self.get_results(query_options=query_options)
        yield tuple(selector.name for selector in self.selectors)
        for result in results:
            yield tuple(getattr(result, selector.name) if hasattr(result, selector.name) else None for selector in self.selectors)

    def schedule(self, schedule_id=None, urls=None):
        schedule_id = schedule_id or str(int(time.time()))

        urls = set(urls) if urls is not None else set(self.get_urls())

        for url in urls:
            while True:  # try until success
                try:
                    taskqueue.add(url="/webscraper/taskqueue/run_task", params=dict(schedule_id=schedule_id, url=url, name=self.key.id()), name=schedule_id+str(hash(url)), queue_name="task", target="1.default")
                    break
                except (taskqueue.DuplicateTaskNameError, taskqueue.TaskAlreadyExistsError, taskqueue.TombstonedTaskError):
                    logging.warning("%s already scheduled" % url)  # only schedule any url once per schedule
                except Exception as e:
                    logging.error("Unexptected scheduling exception. Continue nevertheless: " + e.message)
                    time.sleep(1)

    def run(self, url, schedule_id=None, store=True):
        ## Fetch Result ##
        results = [Result(key=self.get_result_key(value_dict), task_key=self.key, **value_dict) for value_dict in Scraper.http_request(url, selectors=self.selectors) if self.get_result_key(value_dict)]

        if store and results:
            ## Store result in database ##
            ndb.put_multi(results)

            ## Schedule new urls on recursive call ##
            if self.recursive_url_selectors:
                self.schedule(schedule_id=schedule_id, urls=self.recursive_url_selectors[0].get_urls(Query_Options(entities=results)))

        return results

    def test(self):
        return self.run(url=next(self.get_urls(Query_Options(limit=1))), store=False)

    def export(self):
        url_selectors = "[%s\n    ]" % ",".join(["""\n      UrlSelector(url_raw="%s", task_key=ndb.%s, selector_name="%s", start_parameter="%s")""" % (url_selector.url_raw, repr(url_selector.task_key), url_selector.selector_name, url_selector.start_parameter) for url_selector in self.url_selectors])

        selectors = "[%s\n    ]" % ",".join(["""\n      Selector(name="%s", is_key=%s, xpath='''%s''', type=%s, regex="%s")""" % (selector.name, selector.is_key, selector.xpath, Selector.TYPE_REAL_STR[selector.type], selector.regex) for selector in self.selectors])

        return """Task(
    name="%s",
    url_selectors=%s,
    selectors=%s
)""" % (self.name, url_selectors, selectors)

    def export_to_excel(self):
        return Task.export_data_to_excel(data=self.get_results_as_table())

    @staticmethod
    def export_data_to_excel(data):
        import xlwt  # Excel export support
        import io  # for files in memory

        w = xlwt.Workbook()
        ws = w.add_sheet("data")

        ## write ##
        for x, row in enumerate(data):
            for y, column in enumerate(row):
                ws.write(x, y, column)

        ## save ##
        f = io.BytesIO('%s.xls' % "export")
        w.save(f)
        del w, ws
        f.seek(0)
        logging.info("excel file size: %s" % f.__sizeof__())
        return f.read()

    @staticmethod
    def example_tasks():
        return [
            ##### Fußball #####
            Task(
                name="Fussball_Saisons",
                url_selectors=[UrlSelector(url_raw="http://www.transfermarkt.de/3262/kader/verein/3262/", task_key=ndb.Key(Task, "Fussball_Saisons"))],
                selectors=[
                    Selector(name="saison",         xpath="""//select[@name="saison_id"]/option/@value""", type=int, regex=r"20[^\n\r ,.][^\n\r]+", is_key=True),
                ],
            ),
            Task(
                name="Fussball_Spieler",
                url_selectors=[UrlSelector(url_raw="http://www.transfermarkt.de/%s", task_key=ndb.Key(Task, "Fussball_Vereine"), selector_name="verein_url")],
                selectors=[
                    Selector(name="spieler_id",     xpath="""//a[@class="spielprofil_tooltip"]/@href""", type=int, is_key=True),
                ],
            ),
            Task(
                name="Fussball_Spieler_Details",
                url_selectors=[UrlSelector(url_raw="http://www.transfermarkt.de/daten/profil/spieler/%s", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id")],
                selectors=[
                    Selector(name="spieler_id",     xpath="""//link[@rel="canonical"]/@href""", type=int, is_key=True),
                    Selector(name="name",     xpath="""//div[@class="spielername-profil"]/text()""", type=unicode),
                    Selector(name="position",     xpath="""//table[@class="profilheader"]//td[preceding-sibling::th/text()="Position:"]""", type=unicode),
                    Selector(name="max_value",     xpath="""//table[@class="auflistung mt10"]/tr[3]/td/text()""", type=float),
                    Selector(name="birthday",     xpath="""//td[preceding-sibling::th/text()="Geburtsdatum:"]/a/text()""", type=datetime),
                    Selector(name="size",     xpath="""//td[preceding-sibling::th/text()="Größe:"]//text()""", type=float),
                ],
            ),
            Task(
                name="Fussball_Transfers",
                url_selectors=[UrlSelector(url_raw="http://www.transfermarkt.de/daten/profil/spieler/%s", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id")],
                selectors=[
                    Selector(name="spieler_id",     xpath="""(//a[@class="megamenu"])[1]/@href""", type=int),
                    Selector(name="date",     xpath="""(//table)[3]//tr/td[2]//text()""", type=datetime),
                    Selector(name="from",     xpath="""(//table)[3]//tr/td[5]/a/text()""", type=unicode),
                    Selector(name="to",     xpath="""(//table)[3]//tr/td[8]/a/text()""", type=unicode),
                    Selector(name="transfer_key",     xpath="""merge_lists((//a[@class="megamenu"])[1]/@href, (//table)[3]//tr/td[5]/a/text(), (//table)[3]//tr/td[8]/a/text())""", type=unicode, is_key=True),
                ],
            ),
            Task(
                name="Fussball_Vereine",
                url_selectors=[UrlSelector(url_raw="http://www.transfermarkt.de/1-bundesliga/startseite/wettbewerb/L1/saison_id/%s", task_key=ndb.Key(Task, "Fussball_Saisons"), selector_name="saison")],
                selectors=[
                    Selector(name="verein_url",     xpath="""//table[@class='items']//tr/td[@class='hauptlink no-border-links']/a[1]/@href""", type=unicode, is_key=True),
                ],
            ),
            Task(
                name="Fussball_Verletzungen",
                url_selectors=[
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/verletzungen/spieler/%s", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de%s", task_key=ndb.Key(Task, "Fussball_Verletzungen"), selector_name="next_page")],
                selectors=[
                    Selector(name="spieler_id",     xpath="""(//a[@class="megamenu"])[1]/@href""", type=int),
                    Selector(name="injury",     xpath="""//table[@class="items"]//tr/td[2]/text()""", type=unicode),
                    Selector(name="from",     xpath="""//table[@class="items"]//tr/td[3]/text()""", type=datetime),
                    Selector(name="to",     xpath="""//table[@class="items"]//tr/td[4]/text()""", type=datetime),
                    Selector(name="duration",     xpath="""//table[@class="items"]//tr/td[5]/text()""", type=int),
                    Selector(name="missed_games",     xpath="""//table[@class="items"]//tr/td[6]/text()""", type=int),
                    Selector(name="injury_key",     xpath="""merge_lists((//a[@class="megamenu"])[1]/@href, //table[@class="items"]//tr/td[3]/text())""", type=unicode, is_key=True),
                    Selector(name="next_page",     xpath="""//li[@class="naechste-seite"]/a/@href""", type=unicode),
                    Selector(name="club",     xpath="""exe(//table[@class="items"]//tr/td[6],".//@title")""", type=unicode),
                ],
            ),
            Task(
                name="Fussball_Einsaetze",
                url_selectors=[
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2000", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2001", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2002", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2003", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2004", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2005", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2006", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2007", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2008", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2009", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2010", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2011", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2012", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2013", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                    UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/2014", task_key=ndb.Key(Task, "Fussball_Spieler"), selector_name="spieler_id"),
                ],
                selectors=[
                    Selector(name="einsatz_key",     xpath="""merge_lists((//a[@class="megamenu"])[1]/@href, //div[@class="responsive-table"]/table//tr[@class=""]/td[2])""", type=unicode, is_key=True),
                    # for "Verletzungsbedingte Wechsel": //div[@class="responsive-table"]/table//tr[contains(td[16]//@title, "Verletzungsbedingter Wechsel")]/td[2]
                ],
            ),
            ##### Leichtathletik #####
            Task(
                name="Leichtathletik_Sprint_100m_Herren",
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior", task_key=ndb.Key(Task, "Leichtathletik_Sprint_100m_Herren"))],
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
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/athletes", task_key=ndb.Key(Task, "Leichtathletik_Disziplinen"))],
                selectors=[
                    Selector(name="disciplin", xpath="""//select[@id="selectDiscipline"]/option/@value""", type=str, is_key=True),
                ],
            ),
            Task(
                name="Leichtathletik_Athleten",
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/athletes/search?name=&country=&discipline=%s&gender=", task_key=ndb.Key(Task, "Leichtathletik_Disziplinen"), selector_name="disciplin")],
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
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/athletes/athlete=%s", task_key=ndb.Key(Task, "Leichtathletik_Athleten"), selector_name="athlete_id")],
                selectors=[
                    Selector(name="athlete_id", xpath="""//meta[@name="url"]/@content""", type=int),
                    Selector(name="performance", xpath="""//div[@id="panel-progression"]//tr[count(td)>3]//td[2]""", type=float),
                    Selector(name="datetime", xpath="""merge_lists(//div[@id="panel-progression"]//tr[count(td)>3]/td[last()], //div[@id="panel-progression"]//tr[count(td)>3]/td[1])""", type=datetime),
                    Selector(name="place", xpath="""//div[@id="panel-progression"]//tr[count(td)>3]//td[last()-1]""", type=unicode),
                    Selector(name="discipline", xpath="""exe(//div[@id="panel-progression"]//tr[count(td)>3]//td[2], "../preceding::tr/td[@class='sub-title']")""", type=unicode),
                    Selector(name="performance_key", xpath="""merge_lists(//div[@id="panel-progression"]//tr[count(td)>3]/td[last()], //div[@id="panel-progression"]//tr[count(td)>3]/td[1], //meta[@name="url"]/@content)""", type=unicode, is_key=True),
                ],
            ),
            Task(
                name="Leichtathletik_Top_Performance",
                url_selectors=[
                  UrlSelector(url_raw="http://www.iaaf.org%s/1999", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2000", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2001", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2002", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2003", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2004", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2005", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2006", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2007", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2008", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2009", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2010", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2011", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2012", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2013", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter=""),
                  UrlSelector(url_raw="http://www.iaaf.org%s/2014", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", start_parameter="")
                ],
                selectors=[
                  Selector(name="athlete_id", is_key=True, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]//@href''', type=int, regex="\d[\d.,]*"),
                  Selector(name="first_name", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td/a/text()''', type=unicode, regex="[^\n\r ,.][^\n\r]+"),
                  Selector(name="last_name", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td/a/span/text()''', type=unicode, regex="[^\n\r ,.][^\n\r]+"),
                  Selector(name="performance", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td[2]/text()''', type=float, regex="\d[\d.,:]*"),
                  Selector(name="datetime", is_key=True, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td[last()]/text()''', type=datetime, regex="[^\n\r ,.][^\n\r]+"),
                  Selector(name="gender", is_key=False, xpath='''//meta[@property="og:url"]/@content''', type=unicode, regex=".+/([^/]+)/[^/]+/[^/]+"),
                  Selector(name="class", is_key=False, xpath='''//meta[@property="og:url"]/@content''', type=unicode, regex=".+/([^/]+)/[^/]+"),
                  Selector(name="discpiplin", is_key=True, xpath='''//meta[@property="og:url"]/@content''', type=unicode, regex=".+/([^/]+)/[^/]+/[^/]+/[^/]+/[^/]+"),
                  Selector(name="birthday", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td[preceding-sibling::td[position()=1 and ./a]]''', type=datetime, regex="[^\n\r ,.][^\n\r]+"),
                  Selector(name="nation", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td/img/@alt''', type=unicode, regex="[^\n\r ,.][^\n\r]+")
                ]
            ),
            Task(
                name="Leichtathletik_Top_Urls",
                url_selectors=[UrlSelector(url_raw="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior", task_key=ndb.Key(Task, "Leichtathletik_Top_Urls"))],
                selectors=[
                    Selector(name="url", xpath="""//input[@type="radio"]/@value""", type=unicode, is_key=True),
                ],
            ),

            ##### ImmoScout #####
            Task(
                name="Wohnungen",
                url_selectors=[
                    UrlSelector(url_raw="http://www.immobilienscout24.de%s", start_parameter="/Suche/S-T/Wohnung-Miete/Bayern/Muenchen", task_key=ndb.Key(Task, "Wohnungen"), selector_name="naechste_seite"),
                    UrlSelector(url_raw="http://www.immobilienscout24.de%s", start_parameter="/Suche/S-T/Wohnung-Miete/Berlin/Berlin", task_key=ndb.Key(Task, "Wohnungen"), selector_name="naechste_seite"),
                ],
                selectors=[
                    Selector(name="wohnungs_id", xpath="""//span[@class="title"]//a/@href""", type=int, is_key=True),
                    Selector(name="naechste_seite", xpath="""//span[@class="nextPageText"]/..//@href"""),
                ],
            ),
            Task(
                name="Wohnungsdetails",
                url_selectors=[UrlSelector(url_raw="http://www.immobilienscout24.de/expose/%s", task_key=ndb.Key(Task, "Wohnungen"), selector_name="wohnungs_id")],
                selectors=[
                    Selector(name="wohnungs_id", xpath="""//a[@id="is24-ex-remember-link"]/@href""", type=int, is_key=True),
                    Selector(name="postleitzahl", xpath="""//div[@data-qa="is24-expose-address"]//text()""", type=int, regex="\d{5}"),
                    Selector(name="zimmeranzahl", xpath="""//dd[@class="is24qa-zimmer"]//text()""", type=int),
                    Selector(name="wohnflaeche", xpath="""//dd[@class="is24qa-wohnflaeche-ca"]//text()""", type=int),
                    Selector(name="kaltmiete", xpath="""//dd[@class="is24qa-kaltmiete"]//text()""", type=int),
                ],
            ),
        ]