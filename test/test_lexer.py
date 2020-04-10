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
], ids=lambda x:
    x.replace(".", "_").replace(" ", "_") if isinstance(x, str) else "".join(type(i).__name__[0] for i in x))
def test_lexer(input, tokens):
    assert lexer.parse(input) == tokens
