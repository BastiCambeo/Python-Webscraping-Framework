from django.db import models
from datetime import datetime  # date / time support
import time  # performance clocking support
import logging  # support for logging to console (debuggin)
import itertools  # helpers for iterable objects
from idpscraper.models.scraper import http_request  # Own Web-Scraper
from idpscraper.models.selector import *


class Task(models.Model):
    """ A Webscraper Task """

    name = models.TextField(primary_key=True)
    creation_datetime = models.DateTimeField(auto_now_add=True)

    @property
    def key_selectors(self):
        """ Returns all key selectors """
        return [selector for selector in self.selectors if selector.is_key]

    @property
    def recursive_url_selectors(self):
        return filter(lambda url_selector: url_selector.has_dynamic_url and url_selector.task_key == self.key, self.url_selectors)

    def __init__(self, *args, **kwds):
        kwds.setdefault("key", ndb.Key(Task, kwds.pop("name", None)))
        if kwds.get("key").id():
            # Holds only on new creations, not on datastore retrievals #
            kwds.setdefault("selectors", [Selector(is_key=True)])
            kwds.setdefault("url_selectors", [UrlSelector(task_key=kwds.get("key"))])
        super(Task, self).__init__(*args, **kwds)

    def get_selector(self, name):
        for selector in self.selectors:
            if selector.name == name:
                return selector

    def get_urls(self, query_options=None):
        return itertools.chain(*[url_selector.get_urls(query_options=query_options) for url_selector in self.url_selectors])  # Keep generators intact!

    @staticmethod
    def get(name):
        return Task.objects.get(name=name)

    def get_result_key(self, result_value_dict):
        if all([result_value_dict[selector.name] for selector in self.key_selectors]):
            result_id = u" ".join([str(result_value_dict[selector.name]) for selector in self.key_selectors])  # Assemble Result_key from key selectors
            return ndb.Key(Result, self.name + result_id)

    def delete(self):
        self.delete_results()
        self.key.delete()

    def delete_results(self, cursor=None):
        query_options = Query_Options(keys_only=True, limit=1000, cursor=cursor)
        ndb.delete_multi(self.get_results(query_options=query_options))
        if query_options.has_next and query_options.cursor:
            taskqueue.add(url="/webscraper/taskqueue/delete_results", params=dict(name=self.name, cursor=query_options.cursor.urlsafe()))

    def get_results(self, query_options=None):
        query_options = query_options or Query_Options()

        max_page_size = 1000

        if query_options.limit is None or query_options.limit > max_page_size:
            fetch_limit = max_page_size
        else:
            fetch_limit = min(query_options.limit, max_page_size)

        if fetch_limit:
            query_options.entities, query_options.cursor, query_options.has_next = Result.query(Result.task_key == self.key).fetch_page(fetch_limit, keys_only=query_options.keys_only, offset=query_options.offset, start_cursor=query_options.cursor)
            query_options.offset = None
            if query_options.limit:
                query_options.limit -= fetch_limit

            for entity in query_options.entities:
                yield entity

            if query_options.has_next:
                for entity in self.get_results(query_options=query_options):
                    yield entity

    def get_results_as_table(self, query_options=None):
        if not query_options.offset and not query_options.cursor:
            yield tuple(selector.name for selector in self.selectors)

        results = self.get_results(query_options=query_options)

        for result in results:
            yield tuple(getattr(result, selector.name) if hasattr(result, selector.name) else None for selector in self.selectors)

    def schedule(self, schedule_id=None, urls=None):
        schedule_id = schedule_id or str(int(time.time()))

        urls = set(urls) if urls is not None else set(self.get_urls())
        tasks = []

        while len(urls) > 0 or len(tasks) > 0:  # try until success
            # fill tasks up to 100 new tasks #
            for i in range(min(100, len(urls)) - len(tasks)):
                url = urls.pop()
                tasks.append(taskqueue.Task(url="/webscraper/taskqueue/run_task", params=dict(schedule_id=schedule_id, url=url, name=self.key.id()), name=schedule_id + str(hash(url)), target="1.default"))
            try:
                Task.QUEUE.add(tasks)
            except (taskqueue.DuplicateTaskNameError, taskqueue.TaskAlreadyExistsError, taskqueue.TombstonedTaskError):
                logging.warning("%s already scheduled" % url)  # only schedule any url once per schedule
                tasks = [task for task in tasks if not task.was_enqueued][1:]  # remove the first task that was not successful
                continue
            except Exception as e:
                logging.error("Unexptected scheduling exception. Continue nevertheless: " + e.message)
                time.sleep(1)
            tasks = [task for task in tasks if not task.was_enqueued]

    def run(self, url, schedule_id=None, store=True):
        # Fetch Result #
        results = [Result(key=self.get_result_key(value_dict), task_key=self.key, **value_dict) for value_dict in Scraper.http_request(url, selectors=self.selectors) if self.get_result_key(value_dict)]

        if store and results:
            # Store result in database #
            ndb.put_multi(results)

            # Schedule new urls on recursive call #
            if self.recursive_url_selectors:
                self.schedule(schedule_id=schedule_id, urls=self.recursive_url_selectors[0].get_urls(Query_Options(entities=results)))

        return results

    def test(self):
        return self.run(url=next(self.get_urls(Query_Options(limit=1))), store=False)

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
        logging.info("excel file size: %s" % f.__sizeof__())
        return f.read()


    @staticmethod
    def example_tasks()->'list[Task]':
        pass