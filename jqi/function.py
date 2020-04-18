"""
Built-in functions
"""

import inspect


def _truth(x):
    return x is not None and x is not False


REGISTER={}


def register(func):
    name = func.__name__.rstrip("_")
    arity = len(inspect.getfullargspec(func).args) - 2
    REGISTER["{}/{}".format(name, arity)] = func
    return func


@register
def false(env, item):
    return env, [False]


@register
def true(env, item):
    return env, [True]


@register
def null(env, item):
    return env, [None]


@register
def not_(env, item):
    return env, [not _truth(item)]


@register
def empty(env, item):
    return env, []


@register
def select(env, item, test):
    _, vs = test(env, [item])
    return env, [item for v in vs if _truth(v)]
