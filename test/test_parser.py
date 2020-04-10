import pytest
from jqi.parser import parse, Token, Field, Ident, term, exp, Error
from jqi import parser


@pytest.mark.parametrize("input,stream,result", [
    ("", [], []),
    (".", [], []),
    (".", [1, 2, 3], [1, 2, 3]),
    (".a", [1, [1, 2], {"a": "b"}, {}], [Error, Error, "b", Error]),
], ids=lambda x:
    x.replace(".", "_").replace(" ", "_") if isinstance(x, str) else "".join(type(i).__name__[0] for i in x))
def test_term(input, stream, result):
    assert parse(input, start=term)({}, stream) == ({}, result)


def test_field():
    assert parser.field.parse([Field("a")]) == Field("a")


@pytest.mark.parametrize("input,stream,result", [
    ("", [], []),
    (".", [], []),
    (".", [1, 2, 3], [1, 2, 3]),
    (".a", [1, [1, 2], {"a": "b"}, {}], [Error, Error, "b", Error]),
    (".|.", [], []),
    (".|.", [1, 2, 3], [1, 2, 3]),
], ids=lambda x:
    x.replace(".", "_").replace(" ", "_") if isinstance(x, str) else "".join(type(i).__name__[0] for i in x))
def test_exp(input, stream, result):
    assert parse(input, start=exp)({}, stream) == ({}, result)
