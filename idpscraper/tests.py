import doctest
import types
from idpscraper import models


def load_tests(loader, tests, ignore):
    modules = [m for m in models.__dict__.values() if isinstance(m, types.ModuleType)]
    for m in modules:
        tests.addTests(doctest.DocTestSuite(m))
    return tests