import pytest
from jqi.parser import parse, Token, Field, Ident, term, exp, ParseError
from jqi.pattern import *
from jqi.error import Error
from jqi.eval import make_env, comma, literal


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
    (1, ValueMatch("x"), [{"$x": 1}]),
    ([], ValueMatch("x"), [{"$x": []}]),
    ([], ArrayMatch(ValueMatch("x")), [{"$x": None}]),
    ([1], ArrayMatch(ValueMatch("x")), [{"$x": 1}]),
    ([1, 2], ArrayMatch(ValueMatch("x")), [{"$x": 1}]),
    ([[1, 2], [3, 4]],
        ArrayMatch(ValueMatch("x"), ArrayMatch(ValueMatch("y"), ValueMatch("z"))),
        [{"$x": [1, 2], "$y": 3, "$z":4}]),

    # Simple object destructuring
    ({"a": 1, "b": 2, "c": 3},
        ObjectMatch(KeyMatch("a", ValueMatch("A")), KeyMatch("b", ValueMatch("B"))),
        [{"$A": 1, "$B": 2}]),
    # Complex object destructuring
    ({"a": 1, "b": 2, "c": 3},
        ObjectMatch(ExpMatch(comma(literal("a"), literal("b")), ValueMatch("A")), ExpMatch(comma(literal("b"), literal("c")), ValueMatch("C"))),
        [{"$A": 1, "$C": 2}, {"$A": 1, "$C": 3}, {"$A": 2, "$C": 2}, {"$A": 2, "$C": 3}]),
], ids=simplify)
def test_destructure(item, target, result):
    env = make_env()
    stream = [None]
    if isinstance(result, type) and issubclass(result, Exception):
        with pytest.raises(result):
            target.bindings(env, stream, item)
        return
    assert target.bindings(env, stream, item) == result


@pytest.mark.parametrize("input,stream,result", [
    ('. as $x | $x', [1], [1]),
    ('[] as $x | $x', [None], [[]]),
    ('[] as [$x] | $x', [None], [None]),
    ('[1] as [$x] | $x', [None], [1]),
    ('[1, 2] as [$x] | $x', [None], [1]),
    ('[[1, 2], [3, 4]] as [$x, [$y, $z]] | [$x, $y, $z]', [None], [[[1, 2], 3, 4]]),

    # Simple object destructuring
    ('. as {a: $A, b: $B} | [$A, $B]', [{"a": 1, "b": 2, "c": 3}], [[1, 2]]),
    ('. as {$a} | $a', [{"a": 1, "b": 2, "c": 3}], [1]),
    ('. as {a: $A} | $A', [{"a": 1, "b": 2, "c": 3}], [1]),
    ('. as {"a": $A} | $A', [{"a": 1, "b": 2, "c": 3}], [1]),

    # Complex object destructuring
    ('. as {("a", "b"):$A, ("b", "c"):$C} | [$A, $C]', [{"a": 1, "b": 2, "c": 3}], [[1, 2], [1, 3], [2, 2], [2, 3]]),
    ('{"a": 1, "b": 2, "c": 3} as {("a", "b"):$A, ("b", "c"):$C} | [$A, $C]', [None], [[1, 2], [1, 3], [2, 2], [2, 3]]),
], ids=simplify)
def test_parser(input, stream, result):
    if isinstance(result, type) and issubclass(result, Exception):
        with pytest.raises(result):
            parse(input, start=term)
        return
    env = make_env()
    assert parse(input, start=exp)(env, stream) == (env, result)

