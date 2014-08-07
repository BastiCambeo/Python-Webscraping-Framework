__author__ = 'Sebastian Hofstetter'


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

def attr_replace(owner, attr_org, attr_repl):
    """ Replace an attr with a new attr (idempotence guaranteed) """
    if not hasattr(owner, attr_org + "_org"):  # Only replace once
        setattr(owner, attr_org + "_org", getattr(owner, attr_org))  # move original function
        setattr(owner, attr_org, attr_repl)  # Inject new function

def patch_ndb():
    from google.appengine.ext import ndb

    ## Introduce history of values ##
    def model__init__(self, *args, **kwargs):
        ## init is always called on an entity, but without arguments when entity is loaded from database! ##
        self._history_values = {}
        ndb.Model.__init___org(self, *args, **kwargs)
        self._is_initialized = True
    attr_replace(ndb.Model, "__init__", model__init__)


    ## Introduce getters, setters and required-repeated compatibility ##
    def property__init__(self, *args, **kwargs):
        self._validators = kwargs.pop("validators", [])  # checked at put-time
        self._getters = kwargs.pop("getters", [])
        self._setters = kwargs.pop("setters", [])
        if "required" in kwargs and "repeated" in kwargs:
            del kwargs["required"]
            self._required_repeated = True  # circumvent appengine's restriction that required and repeated are mutually exclusive. Only checked at put-time
        ndb.Property.__init___org(self, *args, **kwargs)
    attr_replace(ndb.Property, "__init__", property__init__)


    ## Applies new Getters ##
    def property_get_value(prop, entity):
        value = ndb.Property._get_value_org(prop, entity)
        ## applies new getters ##
        for getter in prop._getters:
            value = getter(entity, value)
        return value
    attr_replace(ndb.Property, "_get_value", property_get_value)


    ## Applies new Setters ##
    def property_set_value(prop, entity, value):
        ## set_value is not called if entity is loaded from database! ##
        ## Setters ##
        for setter in prop._setters:
            value = setter(prop, entity, value)
        ## History Values ##
        if hasattr(entity, "_is_initialized") and prop._code_name not in entity._history_values:  # if entity was initialized: store initialized value (not new value) in _values_history. (When loading from database, the method is not called anyways)
            entity._history_values[prop._code_name] = list(getattr(entity, prop._code_name)) if prop._repeated else getattr(entity, prop._code_name)  # copy mutual datatypes or they will always be updated with their original value
        ndb.Property._set_value_org(prop, entity, value)
    attr_replace(ndb.Property, "_set_value", property_set_value)

    ## Introduce post_load hook (triggers after FETCH and GET) ##
    def query_fetch_async(self, *args, **kwargs):
        def fetch_callback(future):
            if future.state == future.FINISHING and not future._exception:
                for entity in future.get_result():
                    if hasattr(entity, "_post_load_hook"):
                        entity._post_load_hook()  # Call post_load_hook

        future = ndb.Query.fetch_async_org(self, *args, **kwargs)
        future.add_immediate_callback(fetch_callback, future)
        return future
    attr_replace(ndb.Query, "fetch_async", query_fetch_async)

    def key_get_async(self, *args, **kwargs):
        def fetch_callback(future):
            if future.state == future.FINISHING and not future._exception:
                entity = future.get_result()
                if hasattr(entity, "_post_load_hook"):
                    entity._post_load_hook()  # Call post_load_hook
        future = ndb.Key.get_async_org(self, *args, **kwargs)
        future.add_immediate_callback(fetch_callback, future)
        return future
    attr_replace(ndb.Key, "get_async", key_get_async)

import zlib
class zipset(set):
    """ This set does compress its content such that it comes very close to a bloomfilter without false positives """
    def add(self, value, **kwargs):
        return super(zipset, self).add(zlib.compress(value), **kwargs)

