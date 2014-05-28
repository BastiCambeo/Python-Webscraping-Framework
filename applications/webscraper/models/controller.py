import requests  # http support
from lxml import html  # xpath support
import re  # regex support
from pprint import pprint  # pretty print
from requests import Session  # for login required http requests
from gluon.storage import Storage  # easy to use dictioanry
from gluon.scheduler import Scheduler  # for job scheduling
import json  # for storing of dynamically schemed data
import feedparser  # autodetection of date formats
import datetime  # date / time support
import logging  # support for logging to console (debuggin)
import time  # support for sleep
import xlwt  # Excel export support
import os  # support for filesystem and path manipulation
logging.getLogger().setLevel(logging.INFO)

def string_to_float(string):
    first = "," if string.find(",") < string.find(".") else "."
    second = "." if first == "," else ","
    string = string.replace(first, "")  # Remove the thousands separator

    if string.count(second) > 1 or len(string) - string.find(second) == 4:  # If the remaining separator has a count greater than 1 or has exactly 3 digits behind it => it's a thousands separator
        string = string.replace(second, "") # Remove the thousands separator

    string = string.replace(second, ".") # Convert decimal separator to English format

    return float(string)

s = lambda unicode_var: unicode_var.encode("utf-8") if isinstance(unicode_var, unicode) else unicode_var  # use s(unicode) to encode a unicode into a byte string
uni = lambda string_var: string_var if not isinstance(string_var, basestring) and not isinstance(string_var, list) else string_var.decode("utf-8") if not hasattr(string_var, '__iter__') else [s.decode("utf-8") for s in string_var]  # use uni(byte_string_encoded_var) for conversion into unicode

class Task(object):
    _STRING_TYPES = {
        unicode: "string",
        str: "string",
        int: "integer",
        float: "double",
        datetime.datetime: "datetime",
        "string": unicode,
        "integer": int,
        "double": float,
        "datetime": datetime.datetime,
    }

    class Selector(object):  # contains information for selecting a ressource on a xml/html page
        def __init__(self, xpath, name=None, type=None, regex=None):
            regex = ".*" if regex == "None" else regex

            if type and isinstance(type, basestring):
                ## type can be a type or string representation of a type ##
                self.type = Task._STRING_TYPES[type]

            if type in [unicode, str]:
                self.output_cast = type
                regex = regex or "\w[\w\s]*\w|\w"
            elif type == int:
                self.output_cast = lambda s : int(string_to_float(s))
                regex = regex or "\d[\d.,]+"
            elif type == float:
                self.output_cast = string_to_float
                regex = regex or "\d[\d.,]+"
            elif type == datetime.datetime:
                self.output_cast = lambda data: datetime.datetime(*(feedparser._parse_date(data)[:6]))
                regex = regex or "\d+ \w+ \d+"

            self.name = name
            self.xpath = xpath
            self.regex = regex
            self.type = type or unicode


        @property
        def string_type(self):
            return Task._STRING_TYPES[self.type]

        @staticmethod
        def from_task_row(task_row):
            return [Task.Selector(name=task_row.selector_names[i], xpath=task_row.selector_xpaths[i], regex=task_row.selector_regexes[i], type=Task._STRING_TYPES[task_row.selector_types[i]]) for i in range(len(task_row.selector_names))]


    def __init__(self, name, url_generator, selectors, creation_datetime=None, table_name=None, period=0, status=""):
        self.name = name
        self.table_name = table_name or name
        self.url_generator = url_generator
        self.selectors = selectors
        self.period = period
        self.creation_datetime = creation_datetime or datetime.datetime.now()
        self.status = status

    @property
    def is_generated_url(self):
        return "%s" in self.url_generator

    @property
    def urls(self):
        ## url_generator may be a simple string, OR [url containing %s][database-table][database-field]. In the latter case, multiple urls will be created from the given specification. ##
        ## This way it is possible to define recursive crawlers, that successively add new pages to its own urls ##
        if self.is_generated_url:
            url, table, column = self.url_generator[1:-1].split("][")
            rows = db().select(db[table].ALL)
            return set(url % row[column] for row in set(rows) if row[column])  # Convert result into a set to remove duplicates
        else:
            return set(self.url_generator.split(" "))

    @staticmethod
    def _define_tables():
        db.define_table('Task',
            Field("name", type="string", unique=True),
            Field("table_name", type="string"),
            Field("url_generator", type="string"),
            Field("creation_datetime", type="datetime", default=request.now),
            Field("period", type="integer", default=10),  # in seconds
            Field("status", type="string", default=""),
            ## selectors ##
            Field("selector_names", type="list:string"),
            Field("selector_xpaths", type="list:string"),
            Field("selector_regexes", type="list:string"),
            Field("selector_types", type="list:string"),
            redefine=True
        )

        for task_row in db().select(db.Task.ALL):
            fields = [Field(selector.name, type=selector.string_type) for selector in Task.Selector.from_task_row(task_row)]
            db.define_table(task_row.table_name, *fields, redefine=True)

    def put(self):
        """ Serializes the entity into the database """
        kwargs = {
            "name": self.name,
            "table_name": self.table_name,
            "url_generator": self.url_generator,
            "creation_datetime": self.creation_datetime,
            "period": self.period,
            "status": self.status,
            "selector_names": [selector.name for selector in self.selectors],
            "selector_xpaths": [selector.xpath for selector in self.selectors],
            "selector_regexes": [selector.regex for selector in self.selectors],
            "selector_types": [selector.string_type for selector in self.selectors],
        }
        db.Task.update_or_insert(db.Task.name == self.name, **kwargs)

    def delete(self):
        self.unschedule()
        db(db.Task.name == self.name).delete()
        self._define_tables()

    @staticmethod
    def from_task_row(task_row):
        return Task(
            name=task_row.name,
            table_name=task_row.table_name,
            url_generator=task_row.url_generator,
            period=task_row.period,
            status=task_row.status,
            creation_datetime=task_row.creation_datetime,
            selectors=Task.Selector.from_task_row(task_row),
        )

    @staticmethod
    def get_by_name(name):
        try:
            return Task.from_task_row(db.Task(db.Task.name == name))
        except:
            pass

    @staticmethod
    def get_all():
        return [Task.from_task_row(task_row) for task_row in db().select(db.Task.ALL)]

    def schedule(self, repeats=0):
        self.status = "Scheduled"
        self.put()
        self.unschedule()
        scheduler.queue_task('run_by_name', uuid=self.name, pvars=dict(name=self.name), repeats=repeats, period=self.period or 1, immediate=True, retry_failed=0, timeout=10000)  # repeats=0 and retry_failed=-1 means indefinitely

    def unschedule(self):
        db(db.scheduler_task.uuid == self.name).delete()

    def delete_results(self):
        try:
            db[self.table_name].drop()
        except Exception as e:
            pass
        Task._define_tables()

    def get_results(self, with_title=False):
        task_rows = db().select(db[self.table_name].ALL)

        result = [tuple(task_row.as_dict()[selector.name] for selector in self.selectors) for task_row in task_rows]
        if with_title:
            result = [tuple(selector.name for selector in self.selectors)] + result

        return result

    @staticmethod
    def delete_all_results():
        for task in Task.get_all():
            task.delete_results()
        Task._define_tables()

    @staticmethod
    def delete_all_tasks():
        scheduler.terminate_process()
        Task.delete_all_results()
        db.scheduler_task.drop()
        db.scheduler_run.drop()
        db.Task.drop()
        Task._define_tables()

    def run(self, store=True, return_result=False):
        partial_result = result = []
        visited_urls = set()
        remaining_urls = self.urls

        while remaining_urls:  # and len(visited_urls) < 10:  # urls may change during iteration. Therefore for-each is not applicable.
            url = remaining_urls.pop()

            ## Fetch Result ##
            partial_result = Scraper.http_request(url, selectors=self.selectors)
            result += partial_result

            ## Store result in database ##
            if partial_result and store:
                for row in partial_result:
                    row_dict = {self.selectors[i].name: data for i, data in enumerate(row)}  # map selector names and data together
                    db[self.table_name].update_or_insert(**row_dict)

            ## Update urls ##
            visited_urls |= {url}
            remaining_urls = self.urls - visited_urls  # Need to be evaluated after new results have committed (For recursive Crawler)

            ## Log status ##
            if len(visited_urls) != len(remaining_urls)+len(visited_urls):
                self.status = "Progress: %s/%s" % (len(visited_urls), len(remaining_urls)+len(visited_urls))
            else:
                self.status = ""
            self.put()
            logging.warning(self.status)

            ## Must commit any progress such that the recursive crawler can fetch new urls ##
            db.commit()

        if return_result:
            return result

    @staticmethod
    def run_by_name(name, **kwargs):
        return Task.get_by_name(name).run(**kwargs)


class Scraper(object):
    @staticmethod
    def parse(html_src, selectors=None):
        """ Parses an html document for a given XPath expression. Any resulting node can optionally be filtered against a regular expression """

        if not selectors:
            return html_src  # nothing to do

        parsed_tree = html.document_fromstring(html_src)

        selectors_results = []
        for selector in selectors:
            nodes = parsed_tree.xpath(selector.xpath)

            if selector.regex:
                ## Apply regex to every single node ##
                selector_results = []
                for node in nodes:
                    node = unicode(node)
                    regex_result = re.search(selector.regex, node,  re.DOTALL | re.UNICODE)
                    if regex_result:
                        if regex_result.groups():
                            selector_results += [regex_result.groups()[-1]]
                        else:
                            selector_results += [regex_result.group()]
            else:
                selector_results = nodes

            ## auto cast result type##
            if hasattr(selector, "output_cast"):
                selector_results = [selector.output_cast(data) for data in selector_results]
            selectors_results += [selector_results]

        ## convert selector results from a tuple of lists to a list of tuples ##
        result = []
        for y in range(len(selectors_results[0])):
            row = []
            for x in range(len(selectors)):
                row += [selectors_results[x][y]] if y < len(selectors_results[x]) else [None]  # guarantee that an element is added
            result += [row]

        return result

    @staticmethod
    def login(url, user, password):
        """ Returns the session that is yielded by the login """
        session = Session()
        inputs = Scraper.http_request(url, selectors=[Task.Selector(xpath="//input")], session=session)
        inputs[0].value = user  # TODO: more intelligent search for correct user and password field in form
        inputs[1].value = password
        data = {input.name: input.value for input in inputs}
        session.post(url, data)
        return session

    @staticmethod
    def http_request(url, selectors=None, session=None):
        """ Returns the response of an http get-request to a given url """
        logging.warning(url)  # For Debugging purposes
        session = session or Session()
        html_src = session.get(url).text
        return Scraper.parse(html_src, selectors=selectors)