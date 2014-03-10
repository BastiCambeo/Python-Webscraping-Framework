def parse(html_code, xpath, regex=".*"):
    """ Parses an html document for a given XPath expression. Any resulting node can optionally be filtered against a regular expression """
    from lxml import html  # xpath support
    import re  # regex support
    parsed_tree = html.document_fromstring(html_code)
    return [re.search(regex, node,  re.DOTALL).group() for node in parsed_tree.xpath(xpath)]


def load(url):
    """ Returns the response of an http get-request to a given url """
    import requests  # http support
    return requests.get(url).text