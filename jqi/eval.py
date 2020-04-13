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


# Spread a single environment throughout a stream
def evaluate(func, env, stream):
    return func([(env, item) for item in stream])


def pipe(x, y):
    def pipe(env_stream):
        env_stream = x(env_stream)
        return y(env_stream)
    return pipe


def dot(env_stream):
    return env_stream


def comma(x, y):
    def comma(env_stream):
        result = []
        for e_i in env_stream:
            e_r1 = x([e_i])
            result.extend(e_r1)
            e_r2 = y([e_i])
            result.extend(e_r2)
        return result
    return comma


def field(f):
    def access(i):
        if i is None:
            return None     # jq semantics
        try:
            return i.get(str(f))       # ditto for missing fields
        except Exception as e:
            return Error.from_exception(e)

    def _field_access(env_stream):
        return [(e, access(i)) for (e, i) in env_stream]

    return _field_access


def literal(n):
    def _literal(env_stream):
        return [(env, n) for (env, _) in env_stream]

    return _literal


def variable(v):
    ident_name = "${}".format(v)
    def variable(env_stream):
        return [(env, env[ident_name]) for (env, _) in env_stream]
    return variable


def binding(exp, v):
    ident_name = "${}".format(v)
    # TODO: complex destructuring
    def binding(env, stream):
        for item in stream:
            # TODO: refactor so environments are part of the stream!
            raise NotImplementedError()


def _truth(x):
    return x is not None and x is not False


# log_and and log_or have bizarre short-circuiting behaviour
def log_and(xf, yf):
    def log_and(env_stream):
        results = []
        for env1, x in xf(env_stream):
            if _truth(x):
                # XXX: does the environment from the LHS percolate into the environment on the RHS?
                results.extend((env2, _truth(y)) for (env2, y) in yf(env_stream))
            else:
                results.append((env1, False))
        return results
    return log_and


def log_or(xf, yf):
    def log_or(env_stream):
        results = []
        for env1, x in xf(env_stream):
            if _truth(x):
                results.append((env1, True))
            else:
                results.extend((env2, _truth(y)) for (env2, y) in yf(env_stream))
        return results
    return log_or


def op_mul(xf, yf):
    def op_mul(env_stream):
        # Check here: are environments regenerated and passed through?
        return [(e2, x * y) for (e2, y) in yf(env_stream) for (e1, x) in xf(env_stream)]
    return op_mul


def op_add(xf, yf):
    def op_add(env_stream):
        # Check here: are environments regenerated and passed through?
        return [(e2, x + y) for (e2, y) in yf(env_stream) for (e1, x) in xf(env_stream)]
    return op_add


def op_sub(xf, yf):
    def op_sub(env_stream):
        # Check here: are environments regenerated and passed through?
        return [(e2, x - y) for (e2, y) in yf(env_stream) for (e1, x) in xf(env_stream)]
    return op_sub


def call(ident, *argfs):
    # Work out the arity of the function call
    ident_name = "{}/{}".format(ident, len(argfs))

    def apply(env_stream):
        # Check the order of evaluation here
        results = []
        for env, item in env_stream:
            # Call the function with the items from its stream
            fun = env[ident_name]
            # We do this one at a time. The function itself will have to handle the argfs.
            _, result = fun(env, item, *argfs)
            results.extend(result)
        return results

    return apply


def iterate(env_stream):
    result = []
    for env, item in env_stream:
        if isinstance(item, (Number, str, type(None))):
            raise ValueError("can't iterate over {}".format(type(item).__name__))
        elif isinstance(item, list):
            result.extend((env, i) for i in item)
        elif isinstance(item, dict):
            result.extend((env, v) for v in item.values())
        else:
            raise ValueError("can't iterate over {}".format(type(item).__name__))
    return result


def collect(exp):
    def collect(env_stream):
        result = []
        for env, item in env_stream:
            items = exp([(env, item)])
            result.extend(items)
        return result
    return collect


def make_env():
    return {
        "false/0": lambda env, item: [(env, False)],
        "true/0": lambda env, item: [(env, True)],
        "null/0": lambda env, item: [(env, None)],
        "not/0": lambda env, item: [(env, not _truth(item))],
        "empty/0": lambda env, item: [],
    }
