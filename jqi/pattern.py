"""
Destructuring match support
"""

from numbers import Number
from .error import Error
from .lexer import Ident, Str


class Match:
    def bindings(self, env, stream, item):
        # Return a stream of bindings to use
        raise NotImplementedError("bindings")


class ValueMatch(Match):
    def __init__(self, target):
        self.target = target

    def bindings(self, env, stream, item):
        return [{self.target: item}]


class ArrayMatch(Match):
    def __init__(self, *targets):
        self.targets = targets

    def bindings(self, env, stream, item):
        if item is None:
            item = []
        elif not isinstance(item, list):
            raise Error("cannot index {} with number")
        return self._bindings(env, stream, item, self.targets)

    def _bindings(self, env, stream, item, targets):
        if len(targets) == 0:
            return [{}]

        # TODO: null values here
        if len(item) == 0:
            # Bind the rest against None
            results = targets[0].bindings(env, stream, None)
        else:
            results = targets[0].bindings(env, stream, item[0])

        total = []
        for other in self._bindings(env, stream, item[1:], targets[1:]):
            for result in results:
                this_binding = dict(result)
                this_binding.update(other)
                total.append(this_binding)
        return total
