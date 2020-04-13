import pytest
from jqi.parser import parse, Token, Field, Ident, term, exp, ParseError
from jqi.pattern import *
from jqi.error import Error
from jqi.eval import make_env
from jqi import parser


def simplify(x):
    if isinstance(x, str):
        return x.replace(".", "_").replace(" ", "_")
    elif isinstance(x, (list, tuple)):
        return "".join(type(i).__name__[0] for i in x)
    elif isinstance(x, type):
        return x.__name__
    else:
        return type(x).__name__


@pytest.mark.parametrize("item,target,result", [
    (1, ValueMatch("x"), [{"x": 1}]),
    ([], ValueMatch("x"), [{"x": []}]),
    ([], ArrayMatch(ValueMatch("x")), [{"x": None}]),
    ([1], ArrayMatch(ValueMatch("x")), [{"x": 1}]),
    ([1, 2], ArrayMatch(ValueMatch("x")), [{"x": 1}]),
    ([[1, 2], [3, 4]],
        ArrayMatch(ValueMatch("x"), ArrayMatch(ValueMatch("y"), ValueMatch("z"))),
        [{"x": [1, 2], "y": 3, "z":4}]),

], ids=simplify)
def test_destructure(item, target, result):
    env = make_env()
    stream = [None]
    if isinstance(result, type) and issubclass(result, Exception):
        with pytest.raises(result):
            target.bindings(env, stream, item)
        return
    assert target.bindings(env, stream, item) == result

