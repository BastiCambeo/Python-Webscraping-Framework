from datetime import datetime  # date / time support
import time  # performance clocking support
import logging  # support for logging to console (debuggin)
import itertools  # helpers for iterable objects
from gluon.storage import Storage  # Support for dictionary container Storage
from Scraper import Scraper, Selector  # Own Web-Scraper
from util import *  # for generic helpers
from google.appengine.api import taskqueue, memcache, app_identity  # Support for scheduled, cronjob-like tasks and memcache
from google.appengine.ext import ndb, db  # Database support
patch_ndb()

class Result(ndb.Expando):
    """ Holds results of webscraping executions """
    _default_indexed = False
    task_key = ndb.KeyProperty(kind="Task")


class UrlSelector(ndb.Model):
    """ Urls that should be crawled in this task. Can be fetched from the result of other tasks """

    url_raw = ndb.StringProperty(default="")
    task_key = ndb.KeyProperty(kind="Task", required=True)
    selector_name = ndb.StringProperty(default="")
    selector_name2 = ndb.StringProperty(default="")

    def get_urls(self, query_options=None):
        """ Retrieves the urls of an URL Selector (based a result table if the url is dynamic) """

        if self.has_dynamic_url:
            for url_parameters in self.get_url_parameters(query_options=query_options):
                yield self.url_raw % tuple(url_parameters[0: self.url_raw.count("%s")])
        else:
            yield self.url_raw

    def get_url_parameters(self, query_options=None):
        query_options = query_options or Query_Options()
        for result in query_options.entities or self.task_key.get().get_results():
            if getattr(result, self.selector_name) is not None and getattr(result, self.selector_name2) is not None:
                yield [getattr(result, self.selector_name), getattr(result, self.selector_name2)]

    @property
    def has_dynamic_url(self):
        return "%s" in self.url_raw


class Task(ndb.Model):
    """ A Webscraper Task """

    # self.key.id() := name of the tasks
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
        if all([result_value_dict[selector.name] for selector in self.key_selectors]):
            result_id = u" ".join([unicode(result_value_dict[selector.name]) for selector in self.key_selectors])  # Assemble Result_key from key selectors
            return ndb.Key(Result, self.name + result_id)

    def delete(self):
        self.delete_results()
        self.key.delete()

    def delete_results(self):
        result_keys = self.get_results(Query_Options(keys_only=True))
        while True:
            tmp = list(itertools.islice(result_keys, 0, 1000))
            if not tmp:
                return
            ndb.delete_multi(tmp)

    @staticmethod
    def delete_all_results(cursor=None):
        result_keys, next_curs, more = Result.query().fetch_page(1000, start_cursor=cursor, keys_only=True)
        ndb.delete_multi(result_keys)
        if more and next_curs:
            taskqueue.add(url="/webscraper/taskqueue/delete_results", params=dict(cursor=next_curs.urlsafe()))

    def get_results(self, query_options=None):
        query_options = query_options or Query_Options()

        max_page_size = 1000

        if query_options.limit is None or query_options.limit > max_page_size:
            fetch_limit = max_page_size
        else:
            fetch_limit = min(query_options.limit, max_page_size)

        if fetch_limit:
            query_options.entities, query_options.cursor, query_options.has_next = Result.query(Result.task_key == self.key).fetch_page(fetch_limit, keys_only=query_options.keys_only, offset=query_options.offset, start_cursor=query_options.cursor)
            query_options.offset = None
            if query_options.limit:
                query_options.limit -= fetch_limit

            for entity in query_options.entities:
                yield entity

            if query_options.has_next:
                for entity in self.get_results(query_options=query_options):
                    yield entity

    def get_results_as_table(self, query_options=None):
        if not query_options.offset and not query_options.cursor:
            yield tuple(selector.name for selector in self.selectors)

        results = self.get_results(query_options=query_options)

        for result in results:
            yield tuple(getattr(result, selector.name) if hasattr(result, selector.name) else None for selector in self.selectors)

    def schedule(self, schedule_id=None, urls=None):
        schedule_id = schedule_id or str(int(time.time()))

        urls = set(urls) if urls is not None else set(self.get_urls())
        tasks = []

        while len(urls) > 0 or len(tasks) > 0:  # try until success
            ## fill tasks up to 100 new tasks ##
            for i in range(min(100, len(urls))-len(tasks)):
                url = urls.pop()
                tasks.append(taskqueue.Task(url="/webscraper/taskqueue/run_task", params=dict(schedule_id=schedule_id, url=url, name=self.key.id()), name=schedule_id+str(hash(url)), target="1.default"))
            try:
                Task.QUEUE.add(tasks)
            except (taskqueue.DuplicateTaskNameError, taskqueue.TaskAlreadyExistsError, taskqueue.TombstonedTaskError):
                logging.warning("%s already scheduled" % url)  # only schedule any url once per schedule
                tasks = [task for task in tasks if not task.was_enqueued][1:]  # remove the first task that was not successful
                continue
            except Exception as e:
                logging.error("Unexptected scheduling exception. Continue nevertheless: " + e.message)
                time.sleep(1)
            tasks = [task for task in tasks if not task.was_enqueued]

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
        url_selectors = "[%s\n    ]" % ",".join(["""\n      UrlSelector(url_raw="%s", task_key=ndb.%s, selector_name="%s", selector_name2="%s")""" % (url_selector.url_raw, repr(url_selector.task_key), url_selector.selector_name, url_selector.selector_name2) for url_selector in self.url_selectors])

        selectors = "[%s\n    ]" % ",".join(["""\n      Selector(name="%s", is_key=%s, xpath='''%s''', type=%s, regex="%s")""" % (selector.name, selector.is_key, selector.xpath, Selector.TYPE_REAL_STR[selector.type], selector.regex.replace("\\", "\\\\")) for selector in self.selectors])

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

    def export_to_gcs(self):
        """ Creates a file for this task, puts the task's data into the a virtual file. Finally the public url to google cloud storage is returned """

        import cloudstorage as gcs
        bucket_name = app_identity.get_default_gcs_bucket_name()
        object_name = self.name + ".txt"
        bucket = '/' + bucket_name
        filename = bucket + '/' + object_name

        try:
            gcs.delete(filename)
        except Exception as e:
            pass  # File might not exist in the first place

        gcs_file = gcs.open(
            filename,
            mode='w',
            content_type='text/plain',
            options={'x-goog-acl': 'public-read'},
            retry_params=gcs.RetryParams(backoff_factor=1.1)
        )

        ## Write actual content ##
        results = self.get_results_as_table()
        while True:
            result_slice = list(itertools.islice(results, 0, 1000))  # take a slice of 1000 results and write it to file
            if not result_slice:
                break
            gcs_file.write(s("\n".join("\t".join([unicode(value) for value in result]) for result in result_slice)))  # aparently only supports only str, not unicode
        gcs_file.close()


        return self.get_gcs_link()

    def get_gcs_link(self):
        object_name = self.name + ".txt"
        bucket_name = app_identity.get_default_gcs_bucket_name()
        return "https://storage.googleapis.com/%s/%s" % (bucket_name, object_name)


    @staticmethod
    def example_tasks():
        return [
Task(
    name="Fussball_Einsaetze",
    url_selectors=[
      UrlSelector(url_raw="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/%s", task_key=ndb.Key('Task', 'Fussball_Spieler'), selector_name="spieler_id", selector_name2="")
    ],
    selectors=[
      Selector(name="spieler_id", is_key=True, xpath='''(//a[@class="megamenu"])[1]/@href''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="minutes_played", is_key=False, xpath='''//div[@class="responsive-table"]/table//tr/td[2]/following-sibling::*[last()]''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="date", is_key=True, xpath='''//div[@class="responsive-table"]/table//tr/td[2]''', type=datetime, regex="[^\\n\\r ,.][^\\n\\r]+")
    ]
),
Task(
    name="Fussball_Saisons",
    url_selectors=[
      UrlSelector(url_raw="http://www.transfermarkt.de/3262/kader/verein/3262/", task_key=ndb.Key('Task', 'Fussball_Saisons'), selector_name="saison", selector_name2="")
    ],
    selectors=[
      Selector(name="saison", is_key=True, xpath='''//select[@name="saison_id"]/option/@value''', type=int, regex="200[8-9]|201[0-5]")
    ]
),
Task(
    name="Fussball_Spieler",
    url_selectors=[
      UrlSelector(url_raw="http://www.transfermarkt.de/%s", task_key=ndb.Key('Task', 'Fussball_Vereine'), selector_name="verein_url", selector_name2="")
    ],
    selectors=[
      Selector(name="spieler_id", is_key=True, xpath='''//a[@class="spielprofil_tooltip"]/@href''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="saison", is_key=True, xpath='''//select[@name="saison_id"]/option[@selected="selected"]/@value''', type=int, regex="\\d[\\d.,]*")
    ]
),
Task(
    name="Fussball_Spieler_Details",
    url_selectors=[
      UrlSelector(url_raw="http://www.transfermarkt.de/daten/profil/spieler/%s", task_key=ndb.Key('Task', 'Fussball_Spieler'), selector_name="spieler_id", selector_name2="")
    ],
    selectors=[
      Selector(name="spieler_id", is_key=True, xpath='''//link[@rel="canonical"]/@href''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="name", is_key=False, xpath='''//div[@class="spielername-profil"]/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="position", is_key=False, xpath='''//table[@class="profilheader"]//td[preceding-sibling::th/text()="Position:"]''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="max_value", is_key=False, xpath='''//table[@class="auflistung mt10"]/tr[3]/td/text()''', type=float, regex="\\d[\\d.,:]*"),
      Selector(name="birthday", is_key=False, xpath='''//td[preceding-sibling::th/text()="Geburtsdatum:"]/a/text()''', type=datetime, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="size", is_key=False, xpath='''//td[preceding-sibling::th/text()="GrÃ¶ÃŸe:"]//text()''', type=float, regex="\\d[\\d.,:]*"),
      Selector(name="retire_date", is_key=False, xpath='''//table[@class="profilheader"]//td[preceding-sibling::*[.//@title="Karriereende"]]''', type=datetime, regex="[^\\n\\r ,.][^\\n\\r]+")
    ]
),
Task(
    name="Fussball_Transfers",
    url_selectors=[
      UrlSelector(url_raw="http://www.transfermarkt.de/daten/profil/spieler/%s", task_key=ndb.Key('Task', 'Fussball_Spieler'), selector_name="spieler_id", selector_name2="")
    ],
    selectors=[
      Selector(name="spieler_id", is_key=False, xpath='''(//a[@class="megamenu"])[1]/@href''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="date", is_key=False, xpath='''(//table)[3]//tr/td[2]//text()''', type=datetime, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="from", is_key=False, xpath='''(//table)[3]//tr/td[5]/a/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="to", is_key=False, xpath='''(//table)[3]//tr/td[8]/a/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="transfer_key", is_key=True, xpath='''merge_lists((//a[@class="megamenu"])[1]/@href, (//table)[3]//tr/td[5]/a/text(), (//table)[3]//tr/td[8]/a/text())''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+")
    ]
),
Task(
    name="Fussball_Vereine",
    url_selectors=[
      UrlSelector(url_raw="http://www.transfermarkt.de/1-bundesliga/startseite/wettbewerb/L1/saison_id/%s", task_key=ndb.Key('Task', 'Fussball_Saisons'), selector_name="saison", selector_name2="")
    ],
    selectors=[
      Selector(name="verein_url", is_key=True, xpath='''//table[@class='items']//tr/td[@class='hauptlink no-border-links']/a[1]/@href''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+")
    ]
),
Task(
    name="Fussball_Verletzungen",
    url_selectors=[
      UrlSelector(url_raw="http://www.transfermarkt.de/spieler/verletzungen/spieler/%s", task_key=ndb.Key('Task', 'Fussball_Spieler'), selector_name="spieler_id", selector_name2=""),
      UrlSelector(url_raw="http://www.transfermarkt.de%s", task_key=ndb.Key('Task', 'Fussball_Verletzungen'), selector_name="next_page", selector_name2="")
    ],
    selectors=[
      Selector(name="spieler_id", is_key=True, xpath='''(//a[@class="megamenu"])[1]/@href''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="injury", is_key=False, xpath='''//table[@class="items"]//tr/td[2]/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="from", is_key=True, xpath='''//table[@class="items"]//tr/td[3]/text()''', type=datetime, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="to", is_key=False, xpath='''//table[@class="items"]//tr/td[4]/text()''', type=datetime, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="duration", is_key=False, xpath='''//table[@class="items"]//tr/td[5]/text()''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="missed_games", is_key=False, xpath='''//table[@class="items"]//tr/td[6]/text()''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="next_page", is_key=False, xpath='''//li[@class="naechste-seite"]/a/@href''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="club", is_key=False, xpath='''exe(//table[@class="items"]//tr/td[6],".//@title")''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+")
    ]
),
Task(
    name="Leichtathletik_Athleten",
    url_selectors=[
      UrlSelector(url_raw="http://www.iaaf.org/athletes/search?name=&country=&discipline=%s&gender=", task_key=ndb.Key('Task', 'Leichtathletik_Disziplinen'), selector_name="disciplin", selector_name2="")
    ],
    selectors=[
      Selector(name="athlete_id", is_key=True, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[1]//@href''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="first_name", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[1]//a/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="last_name", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[1]/a/span/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="sex", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[2]/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="country", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[3]/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="birthday", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[4]/text()''', type=datetime, regex="[^\\n\\r ,.][^\\n\\r]+")
    ]
),
Task(
    name="Leichtathletik_Disziplinen",
    url_selectors=[
      UrlSelector(url_raw="http://www.iaaf.org/athletes", task_key=ndb.Key('Task', 'Leichtathletik_Disziplinen'), selector_name="disciplin", selector_name2="")
    ],
    selectors=[
      Selector(name="disciplin", is_key=True, xpath='''//select[@id="selectDiscipline"]/option/@value''', type=str, regex="")
    ]
),
Task(
    name="Leichtathletik_Performance",
    url_selectors=[
      UrlSelector(url_raw="http://www.iaaf.org/athletes/athlete=%s", task_key=ndb.Key('Task', 'Leichtathletik_Athleten'), selector_name="athlete_id", selector_name2="")
    ],
    selectors=[
      Selector(name="athlete_id", is_key=False, xpath='''//meta[@name="url"]/@content''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="performance", is_key=False, xpath='''//div[@id="panel-progression"]//tr[count(td)>3]//td[2]''', type=float, regex="\\d[\\d.,:]*"),
      Selector(name="datetime", is_key=False, xpath='''merge_lists(//div[@id="panel-progression"]//tr[count(td)>3]/td[last()], //div[@id="panel-progression"]//tr[count(td)>3]/td[1])''', type=datetime, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="place", is_key=False, xpath='''//div[@id="panel-progression"]//tr[count(td)>3]//td[last()-1]''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="discipline", is_key=False, xpath='''exe(//div[@id="panel-progression"]//tr[count(td)>3]//td[2], "../preceding::tr/td[@class='sub-title']")''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="performance_key", is_key=True, xpath='''merge_lists(//div[@id="panel-progression"]//tr[count(td)>3]/td[last()], //div[@id="panel-progression"]//tr[count(td)>3]/td[1], //meta[@name="url"]/@content)''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+")
    ]
),
Task(
    name="Leichtathletik_Sprint_100m_Herren",
    url_selectors=[
      UrlSelector(url_raw="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior", task_key=ndb.Key('Task', 'Leichtathletik_Sprint_100m_Herren'), selector_name="athlete_id", selector_name2="")
    ],
    selectors=[
      Selector(name="athlete_id", is_key=True, xpath='''//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[4]/a/@href''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="first_name", is_key=False, xpath='''//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[4]/a/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="last_name", is_key=False, xpath='''//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[4]/a/span/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="result_time", is_key=False, xpath='''//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[2]/text()''', type=float, regex="\\d[\\d.,:]*"),
      Selector(name="competition_date", is_key=False, xpath='''//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[9]/text()''', type=datetime, regex="[^\\n\\r ,.][^\\n\\r]+")
    ]
),
Task(
    name="Leichtathletik_Top_Performance",
    url_selectors=[
      UrlSelector(url_raw="http://www.iaaf.org%s/1999", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2000", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2001", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2002", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2003", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2004", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2005", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2006", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2007", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2008", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2009", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2010", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2011", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2012", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2013", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2=""),
      UrlSelector(url_raw="http://www.iaaf.org%s/2014", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="url", selector_name2="")
    ],
    selectors=[
      Selector(name="athlete_id", is_key=True, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]//@href''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="first_name", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td/a/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="last_name", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td/a/span/text()''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="performance", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td[2]/text()''', type=float, regex="\\d[\\d.,:]*"),
      Selector(name="datetime", is_key=True, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td[last()]/text()''', type=datetime, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="gender", is_key=False, xpath='''//meta[@property="og:url"]/@content''', type=unicode, regex=".+/([^/]+)/[^/]+/[^/]+"),
      Selector(name="class", is_key=True, xpath='''//meta[@property="og:url"]/@content''', type=unicode, regex=".+/([^/]+)/[^/]+"),
      Selector(name="discpiplin", is_key=True, xpath='''//meta[@property="og:url"]/@content''', type=unicode, regex=".+/([^/]+)/[^/]+/[^/]+/[^/]+/[^/]+"),
      Selector(name="birthday", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td[preceding-sibling::td[position()=1 and ./a]]''', type=datetime, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="nation", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td/img/@alt''', type=unicode, regex="[^\\n\\r ,.][^\\n\\r]+"),
      Selector(name="area", is_key=False, xpath='''//meta[@property="og:url"]/@content''', type=unicode, regex=".+/([^/]+)/[^/]+/[^/]+/[^/]+"),
      Selector(name="rank", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td[1]''', type=int, regex="\\d[\\d.,]*")
    ]
),
Task(
    name="Leichtathletik_Top_Urls",
    url_selectors=[
      UrlSelector(url_raw="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior", task_key=ndb.Key('Task', 'Leichtathletik_Top_Urls'), selector_name="", selector_name2="")
    ],
    selectors=[
      Selector(name="url", is_key=True, xpath='''//input[@type="radio"]/@value''', type=str, regex="")
    ]
),
Task(
    name="Wohnungen",
    url_selectors=[
      UrlSelector(url_raw="http://www.immobilienscout24.de%s", task_key=ndb.Key('Task', 'Wohnungen'), selector_name="naechste_seite", selector_name2=""),
      UrlSelector(url_raw="http://www.immobilienscout24.de%s", task_key=ndb.Key('Task', 'Wohnungen'), selector_name="naechste_seite", selector_name2="")
    ],
    selectors=[
      Selector(name="wohnungs_id", is_key=True, xpath='''//span[@class="title"]//a/@href''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="naechste_seite", is_key=False, xpath='''//span[@class="nextPageText"]/..//@href''', type=str, regex="")
    ]
),
Task(
    name="Wohnungsdetails",
    url_selectors=[
      UrlSelector(url_raw="http://www.immobilienscout24.de/expose/%s", task_key=ndb.Key('Task', 'Wohnungen'), selector_name="wohnungs_id", selector_name2="")
    ],
    selectors=[
      Selector(name="wohnungs_id", is_key=True, xpath='''//a[@id="is24-ex-remember-link"]/@href''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="postleitzahl", is_key=False, xpath='''//div[@data-qa="is24-expose-address"]//text()''', type=int, regex="\\d{5}"),
      Selector(name="zimmeranzahl", is_key=False, xpath='''//dd[@class="is24qa-zimmer"]//text()''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="wohnflaeche", is_key=False, xpath='''//dd[@class="is24qa-wohnflaeche-ca"]//text()''', type=int, regex="\\d[\\d.,]*"),
      Selector(name="kaltmiete", is_key=False, xpath='''//dd[@class="is24qa-kaltmiete"]//text()''', type=int, regex="\\d[\\d.,]*")
    ]
)
        ]