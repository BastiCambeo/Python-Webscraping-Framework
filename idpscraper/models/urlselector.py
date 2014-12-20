__author__ = 'Sebastian Hofstetter'

from django.db import models
from idpscraper.models.task import Task


class UrlSelector(models.Model):
    """ Urls that should be crawled in this task. Can be fetched from the result of other tasks """

    url_raw = models.TextField()
    task_key = models.ForeignKey(Task)
    selector_name = models.TextField()
    selector_name2 = models.TextField()

    def get_urls(self, query_options=None):
        """ Retrieves the urls of an URL Selector (based a result table if the url is dynamic) """

        if self.has_dynamic_url:
            for url_parameters in self.get_url_parameters(query_options=query_options):
                yield self.url_raw % tuple(url_parameters[0: self.url_raw.count("%s")])
        else:
            yield self.url_raw

    def get_url_parameters(self, query_options=None):
        query_options = query_options or Query_Options()
        for result in query_options.entities or self.task_key.get().get_results():
            if getattr(result, self.selector_name) is not None and getattr(result, self.selector_name2) is not None:
                yield [getattr(result, self.selector_name), getattr(result, self.selector_name2)]

    @property
    def has_dynamic_url(self):
        return "%s" in self.url_raw