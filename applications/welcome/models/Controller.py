def parse(html_code, xpath, regex=".*"):
    from lxml import html
    import re
    parsed_tree = html.document_fromstring(html_code)
    return [re.search(regex, node,  re.DOTALL).group() for node in parsed_tree.xpath(xpath)]

def load(url):
    import urllib2
    response = urllib2.urlopen(url)
    return response.read()