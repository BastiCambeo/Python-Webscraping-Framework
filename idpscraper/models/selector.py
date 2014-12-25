__author__ = 'Sebastian Hofstetter'

from idpscraper.models import converters
from django.db import models


class Selector(models.Model):
    """ Contains information for selecting a ressource on a xml/html page """
    INTEGER = 0
    STRING = 1
    DATETIME = 2
    FLOAT = 3
    TYPE_CHOICES = (
        (INTEGER, "integer"),
        (STRING, "string"),
        (DATETIME, "datetime"),
        (FLOAT, "float")
    )
    REGEX = (
        r"\d[\d.,]*",
        r"[^\n\r ,.][^\n\r]+",
        r"\d[\d.,]*",
        r"\d[\d.,:]*"
    )
    CASTS = (
        converters.str2int,
        lambda x: x,
        converters.str2datetime,
        converters.str2float
    )

    name = models.TextField()
    type = models.IntegerField(choices=TYPE_CHOICES)
    xpath = models.TextField()
    regex = models.TextField(blank=True)
    is_key = models.BooleanField(default=False)
    task = models.ForeignKey('Task')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.regex = self.regex or Selector.REGEX[self.type]

    def __str__(self):
        return self.name

    def cast(self, value):
        return Selector.CASTS[self.type](value)