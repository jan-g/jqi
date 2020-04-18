import pytest
from jqi.parser import parse, Token, Field, Ident, term, exp, ParseError
from jqi.eval import make_env, pipe, binding, literal, variable, splice, unsplice
from jqi.pattern import *


def simplify(x):
    if isinstance(x, str):
        return x.replace(".", "_").replace(" ", "_")
    elif isinstance(x, (list, tuple)):
        return "".join(type(i).__name__[0] for i in x)
    elif isinstance(x, type):
        return x.__name__
    else:
        return type(x).__name__


@pytest.mark.parametrize("input,stream,result", [
    ('. = 2', [1], [2]),
    ('.a = 2', [{}], [{"a": 2}]),
    ('.a.b.c = 2', [{}], [{"a": {"b": {"c": 2}}}]),
    ('.a | .b | .c = 2', [{}], [{"a": {"b": {"c": 2}}}]),
    ('.a.b |.c = 2', [{}], [{"a": {"b": {"c": 2}}}]),
    ('.a | .b.c = 2', [{}], [{"a": {"b": {"c": 2}}}]),
    ('.a."b".c = 2', [{}], [{"a": {"b": {"c": 2}}}]),
    ('.a | . | .c = 2', [{}], [{"a": {"c": 2}}]),
    ('. | (.a, .b) = (1, 2)', [None], [{"a": 1, "b": 1}, {"a": 2, "b": 2}]),
], ids=simplify)
def test_updates(input, stream, result):
    if isinstance(result, type) and issubclass(result, Exception):
        with pytest.raises(result):
            parse(input, start=term)
        return
    env = make_env()
    assert unsplice(parse(input, start=exp)(splice(env, stream))) == result
