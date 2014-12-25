__author__ = 'Sebastian Hofstetter'


def serialize(o):
    """ Serializes any object into primitive types """
    if hasattr(o, "__dict__"):
        return {k: serialize(v) for k, v in o.__dict__.items() if isinstance(k, str) and k[0] != "_"}
    if isinstance(o, list) or isinstance(o, set) or isinstance(o, tuple):
        return [serialize(i) for i in o]
    if isinstance(o, dict):
        return {k: serialize(v) for k, v in o.items()}
    if isinstance(o, int) or isinstance(o, bool) or isinstance(o, str) or isinstance(o, float) or isinstance(o, int):
        return o
    raise NotImplementedError("Handler for this type not implemented")