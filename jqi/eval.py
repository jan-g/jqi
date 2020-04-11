from numbers import Number
from .error import Error


def pipe(x, y):
    def pipe(env, stream):
        env, stream = x(env, stream)
        return y(env, stream)
    return pipe


def dot(env, stream):
    return env, stream


def comma(x, y):
    def comma(env, stream):
        result = []
        for i in stream:
            _, r1 = x(env, [i])
            result.extend(r1)
            _, r2 = y(env, [i])
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


def _truth(x):
    return x is not None and x != False


# log_and and log_or have bizarre short-circuiting behaviour
def log_and(xf, yf):
    def log_and(env, stream):
        env1, xs = xf(env, stream)
        results = []
        for x in xs:
            if _truth(x):
                env2, ys = yf(env1, stream)
                results.extend(_truth(y) for y in ys)
            else:
                results.append(False)
        return env, results
    return log_and


def log_or(xf, yf):
    def log_or(env, stream):
        env1, xs = xf(env, stream)
        results = []
        for x in xs:
            if _truth(x):
                results.append(True)
            else:
                env2, ys = yf(env1, stream)
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
        for item in stream:
            # Call the function with the items from its stream
            # We do this one at a time. The function itself will have to handle the argfs.
            _, result = fun(env, item, *argfs)
            results.extend(result)
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


def make_env():
    return {
        "false/0": lambda env, item: (env, [False]),
        "true/0": lambda env, item: (env, [True]),
        "null/0": lambda env, item: (env, [None]),
        "not/0": lambda env, item: (env, [not _truth(item)]),
    }
