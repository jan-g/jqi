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
import operator

from .error import Error
from .lexer import Field, String
from .function import _truth, REGISTER


def pipe(x, y):
    def pipe(stream):
        stream = x(stream)
        stream = y(stream)
        return stream
    return pipe


def dot(stream):
    return stream


def comma(x, y):
    def comma(stream):
        result = []
        for pair in stream:
            r1s = x([pair])
            result.extend(r1s)
            r2s = y([pair])
            result.extend(r2s)
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

    def _field_access(stream):
        return [(e.child({".path": f}), access(i)) for (e, i) in stream]

    return _field_access


def literal(n):
    if isinstance(n, String):
        n = str(n)
    def _literal(stream):
        return [(e.child({".path": "."}), n) for (e, _) in stream]

    return _literal


def variable(v):
    ident_name = "${}".format(v)
    def variable(stream):
        return [(e.child({".path": "."}), e[ident_name]) for (e, _) in stream]
    return variable


def binding(term, pattern, exp):
    # TODO: complex destructuring
    def binding(stream):
        results = []
        for (env, item) in stream:
            # Work out the value(s) to bind
            values = term([(env, item)])
            for env2, value in values:
                bindings = pattern.bindings(stream, value)
                for binding in bindings:
                    env3 = env.child(binding)
                    items = exp([(env3, item)])
                    results.extend(items)
        return results
    return binding


# log_and and log_or have bizarre short-circuiting behaviour
def log_and(xf, yf):
    def log_and(stream):
        results = []
        xs = xf(stream)
        for e1, x in xs:
            if _truth(x):
                # XXX: does the environment from the LHS percolate into the environment on the RHS?
                ys = yf(stream)
                results.extend((e2, _truth(y)) for (e2, y) in ys)
            else:
                results.append((e1, False))
        return results
    return log_and


def log_or(xf, yf):
    def log_or(stream):
        results = []
        xs = xf(stream)
        for e1, x in xs:
            if _truth(x):
                results.append((e1, True))
            else:
                ys = yf(stream)
                results.extend((e2, _truth(y)) for (e2, y) in ys)
        return results
    return log_or


def op_generic(oper):
    def op_generic(xf, yf):
        def op_mul(stream):
            # Check here: are environments regenerated and passed through?
            xs = xf(stream)
            ys = yf(stream)
            return [(e, oper(x, y)) for (e, y) in ys for (_, x) in xs]
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

    def apply(stream):
        # Check the order of evaluation here
        results = []
        # We do this one at a time. The function itself will have to handle the argfs.
        for env, item in stream:
            fun = env[ident_name]
            # Call the function with the items from its stream
            values = fun(env, item, *argfs)
            results.extend(values)
        return results

    return apply


def iterate(stream):
    result = []
    for env, item in stream:
        if isinstance(item, (Number, str, type(None))):
            raise ValueError("can't iterate over {}".format(type(item).__name__))
        elif isinstance(item, list):
            result.extend((env, i) for i in item)
        elif isinstance(item, dict):
            result.extend((env, i) for i in item.values())
        else:
            raise ValueError("can't iterate over {}".format(type(item).__name__))
    return result


def collect(exp):
    def collect(stream):
        result = []
        for env, item in stream:
            items = exp([(env, item)])
            result.append((env, [i for (_, i) in items]))
        return result
    return collect


def make_dict(pairs):
    def make_dict(stream):
        return _make_dicts(stream, pairs)
    return make_dict


def _make_dicts(stream, pairs):
    if len(pairs) == 0:
        return [(make_env(), {})]
    (k, v), *rest = pairs
    ks = k(stream)
    vs = v(stream)
    remainder = _make_dicts(stream, rest)
    results = []
    for e1, k in ks:
        for e2, v in vs:
            for e3, others in remainder:
                r = {str(k): v}
                r.update(others)
                results.append((e1, r))
    return results


def negate(exp):
    def negate(stream):
        vs = exp(stream)
        return [(e, -v) for (e, v) in vs]
    return negate


# Updates have to construct new objects. In order to do this, we need to use the special `.path` attribute on
# an environment and its parents to work out what we're updating.

def set_path(lhs, rhs):
    def set_path(stream):
        results = []
        for env, item in stream:
            rvalues = rhs([(env, item)])
            for env2, rvalue in rvalues:
                # TODO: construct the updated item and return it
                result = item
                lvalues = lhs([(env, item)])
                for env2, lvalue in lvalues:
                    path = env2.get_path()
                    result = deep_update(result, path, rvalue)
                results.append((env, result))
        return results
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


def splice(env, items):
    return [(env, i) for i in items]


def unsplice(stream):
    return [i for (_, i) in stream]
