"""
Destructuring match support
"""

from numbers import Number
from .error import Error
from .lexer import Ident, Str


class Match:
    def bindings(self, stream, item):
        # Return a stream of bindings to use
        raise NotImplementedError("bindings")


class ValueMatch(Match):
    def __init__(self, target):
        self.target = "${}".format(target)

    def bindings(self, stream, item):
        return [{self.target: item}]


class ArrayMatch(Match):
    def __init__(self, *targets):
        self.targets = targets

    def bindings(self, stream, item):
        if item is None:
            item = []
        elif not isinstance(item, list):
            raise ValueError("cannot index {} with number".format(type(item).__name__))
        return self._bindings(stream, item, self.targets)

    def _bindings(self, stream, item, targets):
        if len(targets) == 0:
            return [{}]

        if len(item) == 0:
            # Bind the rest against None
            results = targets[0].bindings(stream, None)
        else:
            results = targets[0].bindings(stream, item[0])

        total = []
        for other in self._bindings(stream, item[1:], targets[1:]):
            for result in results:
                this_binding = dict(result)
                this_binding.update(other)
                total.append(this_binding)
        return total


class ObjectMatch(Match):
    def __init__(self, *targets):
        self.targets = targets

    def bindings(self, stream, item):
        if item is None:
            item = {}
        elif not isinstance(item, dict):
            raise ValueError("cannot index {} with string".format(type(item).__name__))
        return self._bindings(stream, item, self.targets)

    def _bindings(self, stream, item, targets):
        if len(targets) == 0:
            return [{}]

        results = targets[0].bindings(stream, item)

        total = []
        for result in results:
            for other in self._bindings(stream, item, targets[1:]):
                this_binding = dict(result)
                this_binding.update(other)
                total.append(this_binding)
        return total


class KeyMatch(Match):
    def __init__(self, key, matcher):
        self.key = str(key)
        self.matcher = matcher

    def bindings(self, stream, item):
        if item is None:
            item = {}
        elif not isinstance(item, dict):
            raise ValueError("cannot index {} with string".format(type(item).__name__))
        return self.matcher.bindings(stream, item.get(self.key))


class ExpMatch(Match):
    def __init__(self, exp, matcher):
        self.exp = exp
        self.matcher = matcher

    def bindings(self, stream, item):
        if item is None:
            item = {}
        elif not isinstance(item, dict):
            raise ValueError("cannot index {} with string".format(type(item).__name__))
        results = []
        keys = self.exp(stream)
        for env, key in keys:
            results.extend(self.matcher.bindings(stream, item.get(str(key))))
        return results
