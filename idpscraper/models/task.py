__author__ = 'Sebastian Hofstetter'

from django.db import models
import itertools
from idpscraper.models.scraper import http_request
from idpscraper.models.selector import *
from idpscraper.models.urlselector import UrlSelector
from idpscraper.models.result import Result


class Task(models.Model):
    """ A Webscraper Task """

    name = models.TextField(primary_key=True)
    creation_datetime = models.DateTimeField(auto_now_add=True)

    @property
    def key_selectors(self):
        """ Returns all key selectors """
        return [selector for selector in self.selector_set.all() if selector.is_key]

    @property
    def recursive_url_selectors(self):
        return [url_selector for url_selector in self.urlselector_set.all() if url_selector.has_dynamic_url and url_selector.task_key == self.pk]

    @property
    def results(self):
        return Result.objects.filter(task_key=self.pk)

    def __init__(self, *args, **kwds):
        # Holds only on new creations, not on datastore retrievals #
        kwds.setdefault("selectors", [Selector(is_key=True)])
        kwds.setdefault("url_selectors", [UrlSelector(task_key=self.pk)])
        super(Task, self).__init__(*args, **kwds)

    def get_urls(self, results=None, limit=None):
        return itertools.chain(*[url_selector.get_urls(results=results, limit=limit) for url_selector in self.urlselector_set.all()])  # Keep generators intact!

    @staticmethod
    def get(name):
        return Task.objects.get(pk=name)

    def get_results_as_table(self):
        yield tuple(selector.name for selector in self.selectors)

        for result in self.results:
            yield tuple(getattr(result, selector.name) if hasattr(result, selector.name) else None for selector in self.selectors)

    def run(self, limit=None, store=True)->'list[Result]':
        urls = set(self.get_urls(limit=limit))
        visited_urls = set()
        all_results = []

        while len(urls) > 0:
            url = urls.pop()
            if url not in visited_urls:
                visited_urls.add(url)

                # Fetch Result #
                results = http_request(url, selectors=self.selectors)
                all_results.append(results)

                if store and results:
                    # Store result in database #
                    Result.objects.bulk_create(results)

                    # Schedule new urls on recursive call #
                    if self.recursive_url_selectors:
                        urls.update(self.recursive_url_selectors[0].get_urls(results=results))

        return all_results

    def test(self):
        return self.run(limit=1, store=False)

    def export(self):
        url_selectors = "[%s\n    ]" % ",".join(["""\n      UrlSelector(url_raw="%s", task_key=ndb.%s, selector_name="%s", selector_name2="%s")""" % (url_selector.url_raw, repr(url_selector.task_key), url_selector.selector_name, url_selector.selector_name2) for url_selector in self.url_selectors])

        selectors = "[%s\n    ]" % ",".join(["""\n      Selector(name="%s", is_key=%s, xpath='''%s''', type=%s, regex="%s")""" % (selector.name, selector.is_key, selector.xpath, Selector.TYPE_REAL_STR[selector.type], selector.regex.replace("\\", "\\\\")) for selector in self.selectors])

        return """Task(
    name="%s",
    url_selectors=%s,
    selectors=%s\n)""" % (self.name, url_selectors, selectors)

    def export_to_excel(self):
        return Task.export_data_to_excel(data=self.get_results_as_table())

    @staticmethod
    def export_data_to_excel(data):
        import xlwt  # Excel export support
        import io  # for files in memory

        w = xlwt.Workbook()
        ws = w.add_sheet("data")

        # write #
        for x, row in enumerate(data):
            for y, column in enumerate(row):
                ws.write(x, y, column)

        # save #
        f = io.BytesIO('%s.xls' % "export")
        w.save(f)
        del w, ws
        f.seek(0)
        return f.read()


    @staticmethod
    def example_tasks()->'list[Task]':
        pass