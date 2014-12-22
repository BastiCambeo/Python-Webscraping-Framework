__author__ = 'Sebastian Hofstetter'

from idpscraper.models import converters
from django.db import models


class Type(int):
    def __init__(self):
        raise NotImplementedError


class IntType(Type):
    def __new__(cls, *args, **kwargs):
        return super(IntType, cls).__new__(cls, 0)

    def __init__(self):
        self.regex = r"\d[\d.,]*"

    def __str__(self):
        return "integer"

    def __call__(self, value) -> int:
        return converters.str2int(value)


class StrType(Type):
    def __new__(cls, *args, **kwargs):
        return super(StrType, cls).__new__(cls, 1)

    def __init__(self):
        self.regex = r"[^\n\r ,.][^\n\r]+"

    def __str__(self):
        return "string"

    def __call__(self, value) -> int:
        return value


class DatetimeType(Type):
    def __new__(cls, *args, **kwargs):
        return super(DatetimeType, cls).__new__(cls, 2)

    def __init__(self):
        self.regex = r"\d[\d.,]*"

    def __str__(self):
        return "datetime"

    def __call__(self, value) -> int:
        return converters.str2datetime(value)


class FloatType(Type):
    def __new__(cls, *args, **kwargs):
        return super(FloatType, cls).__new__(cls, 3)

    def __init__(self):
        self.regex = r"\d[\d.,:]*"

    def __str__(self):
        return "float"

    def __call__(self, value) -> int:
        return converters.str2float(value)


class Selector(models.Model):
    """ Contains information for selecting a ressource on a xml/html page """

    TYPES = [IntType(), StrType(), DatetimeType(), FloatType()]

    name = models.TextField()
    type = models.IntegerField()
    xpath = models.TextField()
    regex = models.TextField(blank=True)
    is_key = models.BooleanField(default=False)
    task = models.ForeignKey('Task')

    def __str__(self):
        return self.name