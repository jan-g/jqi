import pytest
from jqi.parser import Token, Field
from jqi.lexer import Cursor, lex
from jqi.completion import complete
from jqi.eval import make_env


def simplify(x):
    if isinstance(x, str):
        return x.replace(".", "_").replace(" ", "_")
    elif isinstance(x, (list, tuple)):
        return "".join(type(i).__name__[0] for i in x)
    elif isinstance(x, type):
        return x.__name__
    else:
        return type(x).__name__


@pytest.mark.parametrize("input,result", [
    (".##", [Token("."), Cursor.CURSOR]),
    ("(.##", [Token("("), Token("."), Cursor.CURSOR]),
    ("(.##)", [Token("("), Token("."), Cursor.CURSOR]),
], ids=simplify)
def test_lexer(input, result):
    # Work out where the cursor is in the input
    cursor = input.index("##")
    input = input[:cursor] + input[cursor + 2:]

    assert lex(input, offset=cursor) == result


