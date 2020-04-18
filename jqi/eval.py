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

from copy import deepcopy
from numbers import Number
import operator

from .error import Error
from .lexer import Field, String
from .function import _truth, REGISTER


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
        return env.child({".path": f}), [access(i) for i in stream]

    return _field_access


def literal(n):
    def _literal(env, stream):
        return env.child({".path": "."}), [n for _ in stream]

    return _literal


def variable(v):
    ident_name = "${}".format(v)
    def variable(env, stream):
        value = env[ident_name]
        return env.child({".path": "."}), [value for _ in stream]
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


def op_generic(oper):
    def op_generic(xf, yf):
        def op_mul(env, stream):
            # Check here: are environments regenerated and passed through?
            _, xs = xf(env, stream)
            _, ys = yf(env, stream)
            return env, [oper(x, y) for y in ys for x in xs]
        return op_mul
    return op_generic


op_mul = op_generic(operator.mul)
op_add = op_generic(operator.add)
op_sub = op_generic(operator.sub)
op_div = op_generic(operator.truediv)
op_mod = op_generic(operator.mod)

op_eq = op_generic(operator.eq)
op_ne = op_generic(operator.ne)
op_le = op_generic(operator.le)
op_lt = op_generic(operator.lt)
op_ge = op_generic(operator.ge)
op_gt = op_generic(operator.gt)


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


def make_dict(pairs):
    def make_dict(env, stream):
        return env, _make_dicts(env, stream, pairs)
    return make_dict


def _make_dicts(env, stream, pairs):
    if len(pairs) == 0:
        return [{}]
    (k, v), *rest = pairs
    _, ks = k(env, stream)
    _, vs = v(env, stream)
    remainder = _make_dicts(env, stream, rest)
    results = []
    for k in ks:
        for v in vs:
            for others in remainder:
                r = {str(k): v}
                r.update(others)
                results.append(r)
    return results


def negate(exp):
    def negate(env, stream):
        _, vs = exp(env, stream)
        return env, [-v for v in vs]
    return negate


# Updates have to construct new objects. In order to do this, we need to use the special `.path` attribute on
# an environment and its parents to work out what we're updating.

def set_path(lhs, rhs):
    def set_path(env, stream):
        results = []
        for item in stream:
            env2, lvalues = lhs(env, [item])
            path = env2.get_path()
            for lvalue in lvalues:
                _, values = rhs(env, stream)
                for value in values:
                    # TODO: construct the updated item and return it
                    result = deep_update(item, path, value)
                    results.append(result)
        return env, results
    return set_path


def deep_update(lhs, path, rhs):
    while path != []:
        step = path[0]
        if step == '.':
            path = path[1:]
            continue
        elif isinstance(step, (Field, String)):
            step = str(step)
            lhs = dict(lhs) if lhs is not None else {}
            orig = lhs.get(step)
            lhs[step] = deep_update(orig, path[1:], rhs)
            return lhs
        else:
            raise NotImplementedError("unrecognised path update")
    return rhs


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
        return self

    def effective_bindings(self):
        b = {}
        if self._parent is not None:
            b = self._parent.effective_bindings()
        b.update(self._dict)
        return {k: b[k] for k in b if not k.startswith(".")}

    def __eq__(self, other):
        if type(self) is not type(other):
            return False
        return self.effective_bindings() == other.effective_bindings()

    def get_path(self):
        step = self._dict.get(".path", ".")
        if step == ".":
            return [step]
        else:
            return self._parent.get_path() + [step]


def make_env():
    bindings = {".path": "."}
    bindings.update(REGISTER)
    return Environment(bindings=bindings)
