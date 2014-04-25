import requests  # http support
from lxml import html  # xpath support
import re  # regex support
from pprint import pprint  # pretty print
from requests import Session  # for login required http requests
from gluon.storage import Storage  # easy to use dictioanry
from gluon.scheduler import Scheduler  # for job scheduling
import json  # for storing of dynamically schemed data

db = DAL('sqlite://storage.sqlite', pool_size=1, check_reserved=['all'])
scheduler = Scheduler(db)

db.define_table('Task',
                Field("name", type="string", unique=True),
                Field("url", type="string"),
                Field("xpath", type="string"),
                Field("regex", type="string"),
                Field("creation_datetime",   type="datetime", default=request.now),
                Field("period", type="integer", default=10),  # in seconds
)
for task in db().select(db.Task.ALL):
    db.define_table(task.name, Field("task_result", type="json"))

def run_task(name):
    task = db.Task(db.Task.name == name)
    ## query for result ##
    result = http_request(task.url, xpath=task.xpath, regex=task.regex)
    ## save result in database ##
    db[name].update_or_insert(task_result=json.dumps(result))
    db.commit()
    return result

def parse(html_src, xpath=None, regex=None):
    """ Parses an html document for a given XPath expression. Any resulting node can optionally be filtered against a regular expression """
    if not xpath:
        return html_src  # nothing to do

    parsed_tree = html.document_fromstring(html_src)
    nodes = parsed_tree.xpath(xpath)

    if regex:
        return [re.search(regex, str(node),  re.DOTALL).group() for node in [str(node) for node in nodes]]  # apply regex to every single node

    return nodes

def login(url, user, password):
    """ Returns the session that is yielded by the login """
    session = Session()
    inputs = http_request(url, xpath="//input", session=session)
    inputs[0].value = user  # TODO: more intelligent search for correct user and password field in form
    inputs[1].value = password
    data = {input.name: input.value for input in inputs}
    session.post(url, data)
    return session

def http_request(url, session=None, xpath=None, regex=None):
    """ Returns the response of an http get-request to a given url """
    session = session or Session()
    html_src = session.get(url).text
    return parse(html_src, xpath=xpath, regex=regex)


