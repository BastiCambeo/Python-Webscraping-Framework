""" The model for a task's result """
__author__ = 'Sebastian Hofstetter'

from django.db import models
from picklefield.fields import PickledObjectField


class Result(models.Model):
    """ Holds results of webscraping executions """
    key = models.TextField(primary_key=True)
    task = models.ForeignKey('Task', related_name='results')
    results = PickledObjectField(default=lambda: dict())

    def __str__(self):
        return repr({k: v for k, v in self.__dict__.items() if k not in ["task_id", "_state", "key"]})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # set no-sql values to result object from .results dict #
        for k, v in self.results.items():
            setattr(self, k, v)

    def save(self, *args, **kwargs):
        # set no-sql values from result object to .results dict #
        self.results = {selector.name: getattr(self, selector.name) for selector in self.task.selectors.all()}
        super().save(*args, **kwargs)

    def get_key(self):
        if all([getattr(self, selector.name) for selector in self.task.selectors.all() if selector.is_key]):
            result_id = u" ".join([str(getattr(self, selector.name)) for selector in self.task.selectors.all() if selector.is_key])  # Assemble Result_key from key selectors
            return self.task.name + result_id