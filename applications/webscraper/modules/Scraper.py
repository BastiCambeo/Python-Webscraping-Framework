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
from google.appengine.api import urlfetch
urlfetch.set_default_fetch_deadline(60)

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

    is_key = ndb.BooleanProperty(default=False)
    name = ndb.StringProperty(default="")
    xpath = ndb.StringProperty(default="")
    def type_setter(prop, self, value):
        if issubclass(value, unicode):
            self.regex = self.regex or r"[^\n\r ,.][^\n\r]+"
        elif issubclass(value, int):
            self.regex = self.regex or r"\d[\d.,]*"
        elif issubclass(value, float):
            self.regex = self.regex or r"\d[\d.,:]*"
        elif issubclass(value, datetime):
            self.regex = self.regex or r"[^\n\r ,.][^\n\r]+"
        return value
    type = ndb.PickleProperty(default=str, setters=[type_setter])
    def regex_setter(prop, self, value):
        if not value:
            return self.regex  # Do not overwrite the regex that is forced by the type
        return value
    regex = ndb.StringProperty(default="", setters=[regex_setter])

    @property
    def output_cast(self):
        if issubclass(self.type, unicode):
            return lambda s: unicode(s) if s is not None else None
        elif issubclass(self.type, int):
            return str2int
        elif issubclass(self.type, float):
            return str2float
        elif issubclass(self.type, datetime):
            return str2datetime
        elif issubclass(self.type, str):
            return lambda data: data


class Scraper(object):
    @staticmethod
    def parse(html_src, selectors=None):
        """ Parses an html document for a given XPath expression. Any resulting node can optionally be filtered against a regular expression """

        from lxml import etree

        def textify(node):
            return (unicode(node.text) if hasattr(node, "text") else unicode(node)).strip()

        def merge_lists(context, *args):
            """ Merge the items of lists at same positions. If one list is shorter, its last element is repeated """
            try:
                return [" ".join([textify(arg[min(i, len(arg)-1)]) for arg in args]) for i in range(max(map(len, args)))]
            except Exception as e:
                return [""]

        def exe(context, nodes, path):
            try:
                return [textify(node.xpath(path).pop()) for node in nodes]
            except Exception as e:
                return [""]

        ns = etree.FunctionNamespace(None)
        ns['merge_lists'] = merge_lists
        ns['exe'] = exe

        if not selectors:
            return html_src  # nothing to do

        parsed_tree = html.document_fromstring(html_src)

        selectors_results = []
        for selector in selectors:
            nodes = parsed_tree.xpath(selector.xpath)
            nodes = [textify(node) for node in nodes]

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
                        selector_results += [None]
            else:
                selector_results = nodes

            ## auto cast result type ##
            if hasattr(selector, "output_cast"):
                selector_results = [selector.output_cast(data) for data in selector_results]

            selectors_results += [selector_results]

        ## convert selector results from a tuple of lists to a list of tuples ##
        result = []
        key_selector = next((selector for selector in selectors if selector.is_key), selectors[0])
        for y in range(len(selectors_results[selectors.index(key_selector)])):  # Take as many results, as there are results for the key selector
            row = Storage()
            for x, selector in enumerate(selectors):
                if not selectors_results[x]: selectors_results[x] = [None]  # Guarantee that an element is there
                row[selector.name] = selectors_results[x][min(y, len(selectors_results[x])-1)]
            result += [row]
        return result

    @staticmethod
    def login(url, user, password):
        """ Returns the session that is yielded by the login """
        session = Session()
        inputs = Scraper.http_request(url, selectors=[Selector(xpath="//input")], session=session)
        inputs[0].value = user  # TODO: more intelligent search for correct user and password field in form
        inputs[1].value = password
        data = {input.name: input.value for input in inputs}
        session.post(url, data)
        return session

    @staticmethod
    def http_request(url, selectors=None, session=None):
        """ Returns the response of an http get-request to a given url """

        time_before = datetime.now()

        session = session or Session()
        html_src = session.get(url, timeout=60).text
        parsing = Scraper.parse(html_src, selectors=selectors)

        logging.info("Requested [%s seconds] %s" % ((datetime.now() - time_before).total_seconds(), url))  # For Debugging purposes
        return parsing