__author__ = 'Basti'

import logging  # logging support
from lxml import html  # xpath support
import re  # regex support
from requests import Session  # for login required http requests

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

            ## auto cast result type ##
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