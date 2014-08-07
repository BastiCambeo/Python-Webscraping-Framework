__author__ = 'Basti'

import logging  # logging support
from lxml import html  # xpath support
import re  # regex support
from requests import Session  # for login required http requests
from gluon.storage import Storage  # For easy dict access
from datetime import datetime  # date / time support
from util import *  # for generic helpers
from google.appengine.ext import ndb  # Database support
patch_ndb()

class Selector(ndb.Model):
    """ Contains information for selecting a ressource on a xml/html page """
    TYPES = [str, unicode, int, float, datetime]
    TYPE_STR = {
        str: "anything",
        unicode: "text",
        int: "integer",
        float: "float value",
        datetime: "date or time"
    }

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

    def get_urls(self, results=None):
        """ Retrieves the urls of an URL Selector (based a result table if the url is dynamic) """
        if self.has_dynamic_url:

            if self.start_parameter:
                yield self.url_raw % self.start_parameter

            results = Result.fetch(self.results_key) if results is None else results
            for result in results:
                if getattr(result, self.results_property) is not None:
                    yield self.url_raw % getattr(result, self.results_property)

        else:
            yield self.url_raw

    @property
    def has_dynamic_url(self):
        return "%s" in self.url_raw


class Scraper(object):
    @staticmethod
    def parse(html_src, selectors=None, return_text=True):
        """ Parses an html document for a given XPath expression. Any resulting node can optionally be filtered against a regular expression """

        if not selectors:
            return html_src  # nothing to do

        parsed_tree = html.document_fromstring(html_src)

        selectors_results = []
        for selector in selectors:
            nodes = parsed_tree.xpath(selector.xpath)

            if return_text:
                nodes = [unicode(node.text) if hasattr(node, "text") else unicode(node) for node in nodes]

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

            ## auto cast result type ##
            if hasattr(selector, "output_cast"):
                selector_results = [selector.output_cast(data) for data in selector_results]
            selectors_results += [selector_results]

        ## convert selector results from a tuple of lists to a list of tuples ##
        result = []
        for y in range(len(selectors_results[0])):
            row = Storage()
            for x, selector in enumerate(selectors):
                row[selector.name] = selectors_results[x][y] if y < len(selectors_results[x]) else None  # guarantee that an element is added
            result += [row]
        return result

    @staticmethod
    def parse(html_src, selectors=None):
        """ Parses an html document for a given XPath expression. Any resulting node can optionally be filtered against a regular expression """

        if not selectors:
            return html_src  # nothing to do

        parsed_tree = html.document_fromstring(html_src)

        selectors_results = []
        for selector in selectors:
            nodes = parsed_tree.xpath(selector.xpath)

            nodes = [unicode(node.text) if hasattr(node, "text") else unicode(node) for node in nodes]

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

            ## auto cast result type ##
            if hasattr(selector, "output_cast"):
                selector_results = [selector.output_cast(data) for data in selector_results]
            selectors_results += [selector_results]

        ## convert selector results from a tuple of lists to a list of tuples ##
        result = []
        for y in range(len(selectors_results[0])):
            row = Storage()
            for x, selector in enumerate(selectors):
                row[selector.name] = selectors_results[x][y] if y < len(selectors_results[x]) else None  # guarantee that an element is added
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