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

db = DAL('sqlite://storage.sqlite', pool_size=1, check_reserved=['all'])
scheduler = Scheduler(db)

class Selector(object):  # contains information for selecting a ressource on a xml/html page
    def __init__(self, xpath, type=None, regex=None):
        self.xpath = xpath
        self.regex = regex
        self.type = type

    @staticmethod
    def from_task(task):
        return [Selector(xpath=task.xpaths[i], regex=task.regexes[i], type=eval(task.types[i])) for i in range(len(task.xpaths))]

db.define_table('Task',
    Field("name", type="string", unique=True),
    Field("url", type="string"),
    Field("xpaths", type="list:string"),
    Field("regexes", type="list:string"),
    Field("types", type="list:string"),
    Field("creation_datetime", type="datetime", default=request.now),
    Field("period", type="integer", default=10),  # in seconds
)
for task in db().select(db.Task.ALL):
    db.define_table(task.name, Field("task_result", type="json"))

def run_task(name):
    task = db.Task(db.Task.name == name)
    ## query for result ##
    result = http_request(task.url, selectors=Selector.from_task(task))
    ## save result in database ##
    db[name].update_or_insert(task_result=json.dumps(result))
    db.commit()
    return result

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

        ## auto cast result type##
        if output_cast:
            result = [output_cast(data) for data in result]
        selector_results += [result]

    ## convert selector results from a tuple of lists to a list of tuples ##
    selector_results = [tuple(selector_results[j][i] for j in range(len(selectors))) for i in range(len(selector_results[0]))]

    return selector_results

def login(url, user, password):
    """ Returns the session that is yielded by the login """
    session = Session()
    inputs = http_request(url, selectors=[Selector(xpath="//input")], session=session)
    inputs[0].value = user  # TODO: more intelligent search for correct user and password field in form
    inputs[1].value = password
    data = {input.name: input.value for input in inputs}
    session.post(url, data)
    return session

def http_request(url, selectors=None, session=None):
    """ Returns the response of an http get-request to a given url """
    session = session or Session()
    html_src = session.get(url).text
    return parse(html_src, selectors=selectors)


