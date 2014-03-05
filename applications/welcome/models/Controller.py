def parse(html_code, xpath):
    from lxml import html
    parsed_tree = html.document_fromstring(html_code)
    return parsed_tree.xpath(xpath)

def load(url):
    import urllib2
    response = urllib2.urlopen(url)
    return response.read()