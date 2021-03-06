import pytest
from jqi.parser import parse, Token, Field, Ident, term, exp, ParseError
from jqi.eval import make_env, pipe, binding, literal, variable, splice
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


def test_variable():
    evaluator = parse("$x", start=exp)
    env = make_env()
    env.update({"$x": 1})
    assert evaluator(splice(env, [None])) == splice(env, [1])


def test_binding():
    env = make_env()
    evaluator = binding(literal(1), ValueMatch("x"), variable("x"))
    result = evaluator(splice(env, [None]))
    expected_env = env.child({"$x": 1})
    assert result == splice(expected_env, [1])
