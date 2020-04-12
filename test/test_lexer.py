import pytest
from jqi.lexer import *


def test_equality():
    assert Token("..") == Token("..")
    assert Token("..") == ".."
    assert ".." == Token("..")
    assert Token("..") != Field("..")


@pytest.mark.parametrize("input,tokens", [
    ("...", [Token(".."), Token(".")]),
    ("", []),
    (" ", []),
    ("1", [1]),
    ("# testing\n1", [1]),
    (".data", [Field("data")]),
    (".data[]", [Field("data"), Token("["), Token("]")]),
    ("and", [Token("and")]),
    (". ", [Token(".")]),
], ids=lambda x:
    x.replace(".", "_").replace(" ", "_") if isinstance(x, str) else "".join(type(i).__name__[0] for i in x))
def test_lexer(input, tokens):
    assert lex(input) == tokens


@pytest.mark.parametrize("input,tokens", [
    ("...", [Token.make((0, "..", 2)), Token.make((2, ".", 3))]),
    ("", []),
    (" ", []),
    ("1", [Int.make((0, 1, 1))]),
    ("# testing\n1", [Int.make((10, 1, 11))]),
    (".data", [Field.make((0, ".data", 5))]),
    (".data[]", [Field.make((0, ".data", 5)), Token.make((5, "[", 6)), Token.make((6, "]", 7))]),
    ("and", [Token.make((0, "and", 3))]),
    (". ", [Token.make((0, ".", 1))]),
], ids=lambda x:
    x.replace(".", "_").replace(" ", "_") if isinstance(x, str) else "".join(type(i).__name__[0] for i in x))
def test_lexer_positions(input, tokens):
    assert lex(input) == tokens
