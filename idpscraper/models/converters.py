__author__ = "Sebastian Hofstetter"

from datetime import datetime
import feedparser
import re
import logging


def str2float(string: str) -> float:
    """
    Supports both German and English formatting including 1000-separators
    >>> str2float("10.000,00")
    10000.0
    >>> str2float("10,000.00")
    10000.0

    Supports formatted times
    >>> str2float("10:30:45,2")
    37845.2
    >>> str2float("30:45,2")
    1845.2

    """
    if not string:
        return None

    if ":" in string:
        # Time #
        string = string.replace(",", ".")  # convert to english separators
        parts = map(float, string.split(":"))  # convert parts into floats
        parts = list(reversed(list(parts)))  # the most significant value should be last
        for i in range(len(parts)):
            parts[i] *= 60**i  # interprete parts as 60-ark number
        return sum(parts)
    else:
        # Float #
        first = "," if string.find(",") < string.find(".") else "."
        second = "." if first == "," else ","
        string = string.replace(first, "")  # Remove the thousands separator

        if string.count(second) > 1 or len(string) - string.find(second) == 4:  # If the remaining separator has a count greater than 1 or has exactly 3 digits behind it => it's a thousands separator
            string = string.replace(second, "")  # Remove the thousands separator

        string = string.replace(second, ".")  # Convert decimal separator to English format

        return float(string)


def str2int(string: str) -> int:
    """
    >>> str2int("2.2")
    2
    """
    f = str2float(string)
    if f is not None:
        f = int(f)
    return f


def _parse_date_german(aDateString):
    """parse a date in dd.mm.yyyy format"""
    # 01.01.2010
    _my_date_pattern = re.compile(r'(\d{,2})\.(\d{,2})\.(\d{4})')

    m = _my_date_pattern.search(aDateString)
    if m is None:
        return None
    day, month, year = m.groups()
    return int(year), int(month), int(day), 0,0,0,0,0,0
feedparser._date_handlers.append(_parse_date_german)

def _parse_date_year_only(aDateString):
    """parse a date in yyyy format"""
    # 1968
    _my_date_pattern = re.compile(r'(\d{4})')

    m = _my_date_pattern.search(aDateString)
    if m is None:
        return None
    day, month, year = 1, 1, m.groups()[0]
    return int(year), int(month), int(day), 0,0,0,0,0,0
feedparser._date_handlers.append(_parse_date_year_only)


def str2datetime(string: str) -> datetime:
    """
    >>> str2datetime("01.01.1990")
    datetime.datetime(1990, 1, 1, 0, 0)

    >>> str2datetime("25 AUG 2012")
    datetime.datetime(2012, 8, 25, 0, 0)

    >>> str2datetime("18 APR 1973")
    datetime.datetime(1973, 4, 18, 0, 0)

    >>> str2datetime("1968")
    datetime.datetime(1968, 1, 1, 0, 0)
    """

    try:
        return datetime(*(feedparser._parse_date(string)[:6]))
    except:
        logging.error("failed to parse %s as date" % repr(string))
        raise
