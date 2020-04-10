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
    (".a##", [Field("a"), Cursor.CURSOR]),
    ("(.##", [Token("("), Token("."), Cursor.CURSOR]),
    ("(.a##", [Token("("), Field("a"), Cursor.CURSOR]),
    ("(.##)", [Token("("), Token("."), Cursor.CURSOR]),
    ("(.a##)", [Token("("), Field("a"), Cursor.CURSOR]),
], ids=simplify)
def test_lexer(input, result):
    # Work out where the cursor is in the input
    cursor = input.index("##")
    input = input[:cursor] + input[cursor + 2:]

    assert lex(input, offset=cursor) == result


@pytest.mark.parametrize("input,stream,result", [
    (".##", [{"a": "b", "aa": "d"}], [Token("."), Field("a"), Field("aa")]),
    (".a##", [{"a": "b", "aa": "d"}], [Field("a"), Field("aa")]),
    ("(.##", [{"a": "b", "aa": "d"}], [Token("."), Field("a"), Field("aa")]),
    (".a.##", [{"a": {"b": "c", "bb": "d"}}], [Field("b"), Field("bb")]),
    (".a.b##", [{"a": {"b": "c", "bb": "d"}}], [Field("b"), Field("bb")]),
    (".a|.##", [{"a": {"b": "c", "bb": "d"}}], [Token("."), Field("b"), Field("bb")]),
    (".a|.b##", [{"a": {"b": "c", "bb": "d"}}], [Field("b"), Field("bb")]),
], ids=simplify)
def test_completion(input, stream, result):
    # Work out where the cursor is in the input
    cursor = input.index("##")
    input = input[:cursor] + input[cursor + 2:]

    if isinstance(result, type) and issubclass(result, Exception):
        with pytest.raises(result):
            complete(input, cursor)
        return
    env = make_env()
    assert complete(input, cursor)(env, stream) == result
