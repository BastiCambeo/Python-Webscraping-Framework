__author__ = 'Sebastian Hofstetter'

from idpscraper.models import converters
from django.db import models
from picklefield.fields import PickledObjectField


class Type():
    def __init__(self):
        raise NotImplementedError

    def __eq__(self, other):
        return type(self) == type(other)


class IntType(Type):
    def __init__(self):
        self.regex = r"\d[\d.,]*"

    def __str__(self):
        return "integer"

    def __call__(self, value) -> int:
        return converters.str2int(value)


class StrType(Type):
    def __init__(self):
        self.regex = r"[^\n\r ,.][^\n\r]+"

    def __str__(self):
        return "string"

    def __call__(self, value) -> int:
        return value


class DatetimeType(Type):
    def __init__(self):
        self.regex = r"\d[\d.,]*"

    def __str__(self):
        return "datetime"

    def __call__(self, value) -> int:
        return converters.str2datetime(value)


class FloatType(Type):
    def __init__(self):
        self.regex = r"\d[\d.,:]*"

    def __str__(self):
        return "float"

    def __call__(self, value) -> int:
        return converters.str2float(value)


class Selector(models.Model):
    """ Contains information for selecting a ressource on a xml/html page """
    INTEGER = IntType()
    STRING = StrType()
    DATETIME = DatetimeType()
    FLOAT = FloatType()
    TYPE_CHOICES = (
        (INTEGER, str(INTEGER),),
        (STRING, str(STRING),),
        (DATETIME, str(DATETIME)),
        (FLOAT, str(FLOAT))
    )

    name = models.TextField()
    type = PickledObjectField(choices=TYPE_CHOICES)
    xpath = models.TextField()
    regex = models.TextField(blank=True)
    is_key = models.BooleanField(default=False)
    task = models.ForeignKey('Task')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.regex = self.regex or self.type.regex

    def __str__(self):
        return self.name