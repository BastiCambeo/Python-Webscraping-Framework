__author__ = "Sebastian Hofstetter"

import logging
from lxml import html, etree  # xpath support
from requests import Session  # for login required http requests
from idpscraper.models.selector import Selector
from idpscraper.models.result import Result
import re


def parse(html_src: str, selectors: 'list[Selector]'=None) -> 'list[Result]':
    """
    Parses an html document for a given XPath expression. Any resulting node can optionally be filtered against a regular expression

    >>> parse(html_src="<html><a> test </a></html>", selectors=[Selector(name="value", type=Selector.STRING, xpath="//text()", is_key=True)])
    [<Result: {'value': 'test'}>]
    """

    def textify(node):
        return (str(node.text) if hasattr(node, "text") else str(node)).strip()

    def merge_lists(context, *args):
        """ Merge the items of lists at same positions. If one list is shorter, its last element is repeated """
        try:
            return [" ".join([textify(arg[min(i, len(arg)-1)]) for arg in args]) for i in range(max(map(len, args)))]
        except Exception as e:
            return [""]

    def exe(context, nodes, path):
        """ Executes a given xpath with each node in the first xpath as context node """
        try:
            return pack([textify(node.xpath(path).pop()) if node.xpath(path) else "" for node in nodes])
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
            # Apply regex to every single node #
            selector_results = []
            for node in nodes:
                node = str(node)
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

        selector_results = [selector.cast(data) for data in selector_results]  # cast to type

        selectors_results.append(selector_results)

    # convert selector results from a tuple of lists to a list of tuples #
    results = []
    key_selectors = [selector for selector in selectors if selector.is_key]
    for y in range(max([len(selectors_results[selectors.index(key_selector)]) for key_selector in key_selectors])):  # Take as many results, as there are results for a key selector
        result = Result()
        for x, selector in enumerate(selectors):
            selectors_results[x] = selectors_results[x] or [None]  # Guarantee that an element is there
            setattr(result, selector.name, selectors_results[x][min(y, len(selectors_results[x])-1)])
        results.append(result)
    return results


def login(url: str, user: str, password: str) -> Session:
    """
    Returns the session that is yielded by the login

    """

    session = Session()
    inputs = http_request(url, selectors=[Selector(xpath="//input")], session=session)
    inputs[0].value = user  # TODO: more intelligent search for correct user and password field in form
    inputs[1].value = password
    data = {input.name: input.value for input in inputs}
    session.post(url, data)
    return session


def http_request(url: str, selectors: 'list[Selector]'=None, session: Session=None) -> 'list[Result]':
    """
    Returns the response of an http get-request to a given url

    """

    session = session or Session()
    html_src = session.get(url, timeout=120).text
    parsing = parse(html_src, selectors=selectors)

    logging.info("Requested %s" % url)  # For Debugging purposes
    return parsing