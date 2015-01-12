__author__ = 'Sebastian Hofstetter'

import itertools
from idpscraper.models import UrlSelector, Selector, Result
from django.db import models
import logging
from lxml import html, etree  # xpath support
from requests import Session  # for login required http requests
import re
import time
import traceback
import datetime


class Task(models.Model):
    """ A Webscraper Task """

    name = models.TextField(primary_key=True)

    @property
    def recursive_url_selectors(self):
        return [url_selector for url_selector in self.url_selectors.all() if url_selector.has_dynamic_url and url_selector.selector_task_id == self.pk]

    def __str__(self):
        return self.name

    def get_urls(self, results=None, limit=None):
        return itertools.chain(*[url_selector.get_urls(results=results, limit=limit) for url_selector in self.url_selectors.all()])  # Keep generators intact!

    @staticmethod
    def get(name):
        return Task.objects.get(pk=name)

    def as_table(self, results):
        yield tuple(selector.name for selector in self.selectors.all())

        for result in results:
            yield tuple(getattr(result, selector.name) if hasattr(result, selector.name) else None for selector in self.selectors.all())

    def run(self, limit=None, store=True) -> 'list[Result]':
        urls = set(self.get_urls(limit=limit))
        visited_urls = set()
        all_results = []

        while len(urls) > 0:
            logging.error("Remaining: %s" % len(urls))
            url = urls.pop()
            if url not in visited_urls:
                visited_urls.add(url)

                # Fetch Result #
                results = self.http_request(url)
                all_results += results

                if store and results:
                    # Store result in database #
                    for result in results:
                        result.save()

                    # Schedule new urls on recursive call #
                    if self.recursive_url_selectors:
                        urls.update(self.recursive_url_selectors[0].get_urls(results=results))

        return all_results

    def test(self):
        return self.run(limit=1, store=False)

    def export(self):
        return ",\n".join([repr(m) for m in [self] + list(self.selectors.all()) + list(self.url_selectors.all())])

    def export_to_excel(self):
        return Task.export_data_to_excel(data=self.as_table(self.results.all()))

    @staticmethod
    def export_data_to_excel(data):
        import xlsxwriter  # Excel export support
        import io  # for files in memory

        output = io.BytesIO()
        w = xlsxwriter.Workbook(output, dict(in_memory=True))
        ws = w.add_worksheet("data")
        ws.set_column('A:Z', 25)  # set more appriate width

        cell_types = {
            repr(type(None)): w.add_format(),
            repr(datetime.datetime): w.add_format(dict(num_format="DD.MM.YYYY")),
            repr(int): w.add_format(dict(num_format="0")),
            repr(float): w.add_format(dict(num_format="0.00")),
            repr(str): w.add_format(dict(num_format="@")),
        }

        # write #
        for x, row in enumerate(data):
            for y, column in enumerate(row):
                ws.write(x, y, column, cell_types[repr(type(column))])

        # save #
        w.close()
        output.seek(0)
        return output.read()


    def __repr__(self):
        fields = ["name"]
        fields = ", ".join(["%s=%s" % (f, repr(getattr(self, f))) for f in fields])
        return "Task(%s)" % fields

    def parse(self, html_src: str) -> 'list[Result]':
        """
        Parses an html document for a given XPath expression. Any resulting node can optionally be filtered against a regular expression

        """

        def textify(node):
            return (str(node.text) if hasattr(node, "text") else str(node)).strip()

        def merge_lists(context, *args):
            """ Merge the items of lists at same positions. If one list is shorter, its last element is repeated """
            try:
                return [" ".join([textify(arg[min(i, len(arg) - 1)]) for arg in args]) for i in range(max(map(len, args)))]
            except Exception as e:
                return [""]

        def exe(context, nodes, path):
            """ Executes a given xpath with each node in the first xpath as context node """
            try:
                return [textify(node.xpath(path).pop()) if node.xpath(path) else "" for node in nodes]
            except Exception as e:
                return [""]


        ns = etree.FunctionNamespace(None)
        ns['merge_lists'] = merge_lists
        ns['exe'] = exe

        if not self.selectors.all():
            return html_src  # nothing to do

        parsed_tree = html.document_fromstring(html_src)

        selectors_results = []
        for selector in self.selectors.all():
            nodes = parsed_tree.xpath(selector.xpath)
            nodes = [textify(node) for node in nodes]

            if selector.regex:
                # Apply regex to every single node #
                selector_results = []
                for node in nodes:
                    node = str(node)
                    regex_result = re.search(selector.regex, node, re.DOTALL | re.UNICODE)
                    if regex_result:
                        if regex_result.groups():
                            selector_results += [regex_result.groups()[-1]]
                        else:
                            selector_results += [regex_result.group()]
                    else:
                        selector_results += [None]
            else:
                selector_results = nodes

            selector_results = [selector.cast(data) if data is not None else None for data in selector_results]  # cast to type

            selectors_results.append(selector_results)

        # convert selector results from a tuple of lists to a list of tuples #
        results = []
        for y in range(max([len(selectors_results[list(self.selectors.all()).index(key_selector)]) for key_selector in self.selectors.all() if key_selector.is_key])):  # Take as many results, as there are results for a key selector
            result = Result(task_id=self.name)
            for x, selector in enumerate(self.selectors.all()):
                selectors_results[x] = selectors_results[x] or [None]  # Guarantee that an element is there
                setattr(result, selector.name, selectors_results[x][min(y, len(selectors_results[x]) - 1)])

            result.key = result.get_key(self)
            if result.key:
                results.append(result)

        return results

    def login(self, url: str, user: str, password: str) -> Session:
        """
        Returns the session that is yielded by the login

        """

        session = Session()
        inputs = self.http_request(url, session=session)
        inputs[0].value = user  # TODO: more intelligent search for correct user and password field in form
        inputs[1].value = password
        data = {input.name: input.value for input in inputs}
        session.post(url, data)
        return session

    def http_request(self, url: str, session: Session=None) -> 'list[Result]':
        """
        Returns the response of an http get-request to a given url

        """
        success = False

        while not success:
            try:
                logging.error("Requested %s" % url)  # For Debugging purposes
                session = session or Session()
                html_src = session.get(url, timeout=120).text
                parsing = self.parse(html_src)
                success = True
            except Exception as e:
                traceback.print_exc()
                time.sleep(5)

        return parsing
