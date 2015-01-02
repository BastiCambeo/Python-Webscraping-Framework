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

    task = models.ForeignKey('Task', related_name='selectors')
    name = models.TextField()
    type = models.IntegerField(choices=TYPE_CHOICES, default=STRING)
    xpath = models.TextField()
    regex = models.TextField()
    is_key = models.BooleanField(default=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.regex = self.regex or Selector.REGEX[self.type]

    def __str__(self):
        return self.name

    def cast(self, value):
        return Selector.CASTS[self.type](value)

    def __repr__(self):
        fields = ["task_id", "name", "type", "xpath", "regex", "is_key"]
        fields = ", ".join(["%s=%s" % (f, repr(getattr(self, f))) for f in fields])
        return "Selector(%s)" % fields