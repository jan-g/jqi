"""
Note: there are currently three shortcomings with this implementation.

The first is that we use materialised streams (ie, lists) and pass those around. It's not difficult
to replace these with generators. The main issue with the current implementation is that it makes
functions like `input` near-impossible to implement simply.

The second issue is that we use the Python stack to manage the stack of filters.
This has some small advantages (exception management can lean on Python's implementation); however,
it precludes optimisations like tail recursion.

The third issue is that we don't keep track of query paths. This makes update operators currently
impossible to implement.

In time, all of these will be addressed (probably together).
"""

from numbers import Number
from .error import Error


def pipe(x, y):
    def pipe(env, stream):
        env, stream = x(env, stream)
        env, stream = y(env, stream)
        return env, stream
    return pipe


def dot(env, stream):
    return env, stream


def comma(x, y):
    def comma(env, stream):
        result = []
        for item in stream:
            _, r1 = x(env, [item])
            result.extend(r1)
            _, r2 = y(env, [item])
            result.extend(r2)
        return env, result
    return comma


def field(f):
    def access(i):
        if i is None:
            return None     # jq semantics
        try:
            return i.get(str(f))       # ditto for missing fields
        except Exception as e:
            return Error.from_exception(e)

    def _field_access(env, stream):
        return env, [access(i) for i in stream]

    return _field_access


def literal(n):
    def _literal(env, stream):
        return env, [n for _ in stream]

    return _literal


def variable(v):
    ident_name = "${}".format(v)
    def variable(env, stream):
        value = env[ident_name]
        return env, [value for _ in stream]
    return variable


def binding(term, pattern, exp):
    # TODO: complex destructuring
    def binding(env, stream):
        results = []
        for item in stream:
            # Work out the value(s) to bind
            _, values = term(env, [item])
            for value in values:
                bindings = pattern.bindings(env, stream, value)
                for binding in bindings:
                    env2 = env.child(binding)
                    _, items = exp(env2, [item])
                    results.extend(items)
        return env, results
    return binding


def _truth(x):
    return x is not None and x is not False


# log_and and log_or have bizarre short-circuiting behaviour
def log_and(xf, yf):
    def log_and(env, stream):
        results = []
        _, xs = xf(env, stream)
        for x in xs:
            if _truth(x):
                # XXX: does the environment from the LHS percolate into the environment on the RHS?
                _, ys = yf(env, stream)
                results.extend(_truth(y) for y in ys)
            else:
                results.append(False)
        return env, results
    return log_and


def log_or(xf, yf):
    def log_or(env, stream):
        results = []
        _, xs = xf(env, stream)
        for x in xs:
            if _truth(x):
                results.append(True)
            else:
                _, ys = yf(env, stream)
                results.extend(_truth(y) for y in ys)
        return env, results
    return log_or


def op_mul(xf, yf):
    def op_mul(env, stream):
        # Check here: are environments regenerated and passed through?
        _, xs = xf(env, stream)
        _, ys = yf(env, stream)
        return env, [x * y for y in ys for x in xs]
    return op_mul


def op_add(xf, yf):
    def op_add(env, stream):
        # Check here: are environments regenerated and passed through?
        _, xs = xf(env, stream)
        _, ys = yf(env, stream)
        return env, [x + y for y in ys for x in xs]
    return op_add


def op_sub(xf, yf):
    def op_sub(env, stream):
        # Check here: are environments regenerated and passed through?
        _, xs = xf(env, stream)
        _, ys = yf(env, stream)
        return env, [x - y for y in ys for x in xs]
    return op_sub


def call(ident, *argfs):
    # Work out the arity of the function call
    ident_name = "{}/{}".format(ident, len(argfs))

    def apply(env, stream):
        # Check the order of evaluation here
        results = []
        fun = env[ident_name]
        # We do this one at a time. The function itself will have to handle the argfs.
        for item in stream:
            # Call the function with the items from its stream
            _, values = fun(env, item, *argfs)
            results.extend(values)
        return env, results

    return apply


def iterate(env, stream):
    result = []
    for item in stream:
        if isinstance(item, (Number, str, type(None))):
            raise ValueError("can't iterate over {}".format(type(item).__name__))
        elif isinstance(item, list):
            result.extend(item)
        elif isinstance(item, dict):
            result.extend(item.values())
        else:
            raise ValueError("can't iterate over {}".format(type(item).__name__))
    return env, result


def collect(exp):
    def collect(env, stream):
        result = []
        for item in stream:
            _, items = exp(env, [item])
            result.append(items)
        return env, result
    return collect


class Environment:
    def __init__(self, parent=None, bindings=None):
        if bindings is None:
            bindings = {}
        self._dict = bindings
        self._parent = parent

    def child(self, bindings=None):
        return self.__class__(parent=self, bindings=bindings)

    def __getitem__(self, item):
        try:
            return self._dict[item]
        except KeyError:
            if self._parent is not None:
                return self._parent[item]
            raise

    def __setitem__(self, item, value):
        self._dict[item] = value

    def update(self, d):
        self._dict.update(d)


def make_env():
    return Environment(bindings={
        "false/0": lambda env, item: (env, [False]),
        "true/0": lambda env, item: (env, [True]),
        "null/0": lambda env, item: (env, [None]),
        "not/0": lambda env, item: (env, [not _truth(item)]),
        "empty/0": lambda env, item: (env, []),
    })
