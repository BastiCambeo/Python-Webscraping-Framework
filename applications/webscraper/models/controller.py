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
            self.name = name
            self.xpath = xpath
            self.regex = None if regex == "None" else regex

            ## type can be a type or string representation of a type ##
            if isinstance(type, basestring):
                self.type = Task._STRING_TYPES[type]
            else:
                self.type = type

        @property
        def string_type(self):
            return Task._STRING_TYPES[self.type]

        @staticmethod
        def from_task_row(task_row):
            return [Task.Selector(name=task_row.selector_names[i], xpath=task_row.selector_xpaths[i], regex=task_row.selector_regexes[i], type=Task._STRING_TYPES[task_row.selector_types[i]]) for i in range(len(task_row.selector_names))]


    def __init__(self, name, url, period, selectors, creation_datetime=None):
        self.name = name
        self.url = url
        self.selectors = selectors
        self.period = period
        self.creation_datetime = None or datetime.datetime.now()

    @staticmethod
    def _define_tables():
        db.define_table('Task',
            Field("name", type="string", unique=True),
            Field("url", type="string"),
            Field("creation_datetime", type="datetime", default=request.now),
            Field("period", type="integer", default=10),  # in seconds
            ## selectors ##
            Field("selector_names", type="list:string"),
            Field("selector_xpaths", type="list:string"),
            Field("selector_regexes", type="list:string"),
            Field("selector_types", type="list:string"),
        )

        for task_row in db().select(db.Task.ALL):
            fields = [Field(selector.name, type=selector.string_type) for selector in Task.Selector.from_task_row(task_row)]
            db.define_table(task_row.name, *fields)

    def put(self):
        """ Serializes the entity into the database """
        kwargs = {
            "name": self.name,
            "url": self.url,
            "creation_datetime": self.creation_datetime,
            "period": self.period,
            "selector_names": [selector.name for selector in self.selectors],
            "selector_xpaths": [selector.xpath for selector in self.selectors],
            "selector_regexes": [selector.regex for selector in self.selectors],
            "selector_types": [selector.string_type for selector in self.selectors],
        }
        db.Task.update_or_insert(db.Task.name == self.name, **kwargs)

    @staticmethod
    def from_task_row(task_row):
        return Task(
            name=task_row.name,
            url=task_row.url,
            period=task_row.period,
            creation_datetime=task_row.creation_datetime,
            selectors=Task.Selector.from_task_row(task_row),
        )

    @staticmethod
    def get_by_name(name):
        return Task.from_task_row(db.Task(db.Task.name == name))

    @staticmethod
    def get_all():
        return [Task.from_task_row(task_row) for task_row in db().select(db.Task.ALL)]

    def schedule(self):
        db(db.scheduler_task.uuid == self.name).delete()
        scheduler.queue_task('run_by_name', uuid=task.name, pvars=dict(name=task.name), repeats=0, period=task.period, immediate=True, retry_failed=-1)  # repeats=0 and retry_failed=-1 means indefinitely

    def delete_results(self):
        try:
            db[self.name].drop()
        except Exception as e:
            pass

    def get_results(self):
        task_rows = db().select(db[self.name].ALL)
        return [tuple(task_row.as_dict()[selector.name] for selector in self.selectors) for task_row in task_rows]

    @staticmethod
    def delete_all_results():
        for task in Task.get_all():
            task.delete_results()

    def run(self, store=True, data_modifier=lambda x: x, return_result=False):
        result = Scraper.http_request(self.url, selectors=self.selectors)
        ## save result in database ##
        if result and store:
            for row in result:
                row_dict = {self.selectors[i].name: data_modifier(data) for i, data in enumerate(row)}  # map selector names and data together
                db[self.name].update_or_insert(**row_dict)
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

        selector_results = []
        for selector in selectors:
            nodes = parsed_tree.xpath(selector.xpath)

            if selector.type in [unicode, str]:
                output_cast = selector.type
                selector.regex = selector.regex or "\w+"
            elif selector.type == int:
                output_cast = selector.type
                selector.regex = selector.regex or "\d+"
            elif selector.type == float:
                output_cast = selector.type
                selector.regex = selector.regex or "\d+\.\d+"
            elif selector.type is datetime.datetime:
                output_cast = selector.type = lambda data : datetime.datetime(*(feedparser._parse_date(data)[:6]))
                selector.regex = selector.regex or "\d+ \w+ \d+"

            if selector.regex:
                result = [re.search(selector.regex, node,  re.DOTALL | re.UNICODE).group() for node in [unicode(node) for node in nodes] if re.search(selector.regex, node,  re.DOTALL)]  # apply regex to every single node
            else:
                result = nodes

            ## auto cast result type##
            if output_cast:
                result = [output_cast(data) for data in result]
            selector_results += [result]

        ## convert selector results from a tuple of lists to a list of tuples ##
        selector_results = [tuple(selector_results[j][i] for j in range(len(selectors))) for i in range(len(selector_results[0]))]

        return selector_results

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
        session = session or Session()
        html_src = session.get(url).text
        return Scraper.parse(html_src, selectors=selectors)