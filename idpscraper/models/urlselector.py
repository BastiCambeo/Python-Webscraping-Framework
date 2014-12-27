__author__ = 'Sebastian Hofstetter'

from django.db import models


class UrlSelector(models.Model):
    """ Urls that should be crawled in this task. Can be fetched from the result of other tasks """

    url = models.TextField()
    task = models.ForeignKey('Task')
    selector_task = models.ForeignKey('Task', related_name='related_url_selectors')
    selector_name = models.TextField()
    selector_name2 = models.TextField()

    @property
    def has_dynamic_url(self):
        return "%s" in self.url

    def __str__(self):
        return self.url

    def get_urls(self, results: 'list[Result]'=None, limit=None) -> 'list[str]':
        """ Retrieves the urls of an URL Selector (based a result table if the url is dynamic) """
        if self.has_dynamic_url:
            for url_parameters in self.get_url_parameters(results=results, limit=limit):
                yield self.url % tuple(url_parameters[0: self.url.count("%s")])
        else:
            yield self.url

    def get_url_parameters(self, results: 'list[Result]'=None, limit=None) -> 'list[str]':
        results = results or self.selector_task.results

        if limit:
            results = results[:limit]

        for result in results:
            if getattr(result, self.selector_name) is not None and getattr(result, self.selector_name2) is not None:
                yield [getattr(result, self.selector_name), getattr(result, self.selector_name2)]

    def __repr__(self):
        fields = ["task_id", "url", "selector_task_id", "selector_name", "selector_name2"]
        fields = ", ".join(["%s=%s" % (f, repr(getattr(self, f))) for f in fields])
        return "UrlSelector(%s)" % fields