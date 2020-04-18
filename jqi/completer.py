import functools
from numbers import Number
from .parser import Field, Token, Ident, PartialString, String


class Completion(Exception):
    def __init__(self, completions=None, pos=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.completions = completions
        self.pos = pos


# return the union of keys of objects in the stream
def sample_objects(stream):
    keys = set()
    for env, item in stream:
        try:
            keys.update(item.keys())
        except AttributeError:
            pass
    return sorted(keys)


def field_name(k):
    if k.isalnum():
        return Field(k)
    else:
        return String(k)


def complete_term(term, evaluator):
    if term == Token("."):
        pos = (term.start + 1, term.end)
        def complete_term(stream):
            samples = sample_objects(stream)
            raise Completion(completions=[Token("")] + [field_name(k) for k in samples], pos=pos)
        return complete_term
    elif isinstance(term, (Field, PartialString)):
        def complete_term(stream):
            samples = sample_objects(stream)
            raise Completion(completions=[field_name(k) for k in samples if k.startswith(term)], pos=term.pos)
        return complete_term
    else:
        return evaluator


def complete_field(prefix, evaluator):
    def complete_field(stream):
        stream = evaluator(stream)
        samples = sample_objects(stream)
        raise Completion(completions=[field_name(k) for k in samples if k.startswith(prefix)], pos=prefix.pos)
    return complete_field


def complete_comparison(evaluator):
    def complete_comparison(stream):
        stream = evaluator(stream)
        samples = sample_values(stream)
        raise Completion(completions=[value for value in samples], pos=None)
    return complete_comparison


def sample_values(stream):
    items = set()
    for env, item in stream:
        if isinstance(item, (Number, str)):
            items.add(item)
    return sorted(items, key=functools.cmp_to_key(jq_cmp))


def jq_cmp(x, y):
    """
    null
    false
    true
    numbers
    strings, in alphabetical order (by unicode codepoint value)
    arrays, in lexical order
    objects
    """
    if x is None:
        return 0 if y is None else -1
    if y is None:
        return 1

    if x is False:
        return 0 if y is False else -1
    if y is False:
        return 1

    if x is True:
        return 0 if y is True else -1
    if y is True:
        return 1

    if isinstance(x, Number):
        return (x > y) - (x < y) if isinstance(y, Number) else -1
    if isinstance(y, Number):
        return 1

    if isinstance(x, str):
        return (x > y) - (x < y) if isinstance(y, str) else -1
    if isinstance(y, str):
        return 1

    raise NotImplementedError("can't yet compare types {} and {}".format(type(x), type(y)))

