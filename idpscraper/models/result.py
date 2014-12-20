__author__ = 'Sebastian Hofstetter'

from django.db import models


class Result(models.Model):
    """ Holds results of webscraping executions """
    task_key = models.ForeignKey("Task")