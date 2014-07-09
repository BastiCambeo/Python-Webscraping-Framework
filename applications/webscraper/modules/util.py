__author__ = 'Basti'


def s(unicode_var):
    """ Converts unicode to utf-8 encoded string """
    if isinstance(unicode_var, unicode):
        unicode_var.encode("utf-8")
    return unicode_var


def uni(string_var):
    """ Converts string to unicode """
    if hasattr(string_var, '__iter__'):
        return [uni(v) for v in string_var]
    elif isinstance(string_var, basestring):
        return string_var.decode("utf-8")
    return string_var


def str2float(string):
    """ Respects both German and English formatatting inclding 1000-separators """
    first = "," if string.find(",") < string.find(".") else "."
    second = "." if first == "," else ","
    string = string.replace(first, "")  # Remove the thousands separator

    if string.count(second) > 1 or len(string) - string.find(second) == 4:  # If the remaining separator has a count greater than 1 or has exactly 3 digits behind it => it's a thousands separator
        string = string.replace(second, "")  # Remove the thousands separator

    string = string.replace(second, ".")  # Convert decimal separator to English format

    return float(string)


class omnimethod(object):
    """ Allows to use a method as both staticmethod and instancemethod """
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        import functools
        return functools.partial(self.func, instance)