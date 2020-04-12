import pytest
from jqi.parser import Token, Field, PartialString
from jqi.lexer import Cursor, lex
from jqi.completion import completer


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
    ('"abc##', [PartialString("abc"), Cursor.CURSOR]),
], ids=simplify)
def test_lexer(input, result):
    # Work out where the cursor is in the input
    cursor = input.index("##")
    input = input[:cursor] + input[cursor + 2:]

    assert lex(input, offset=cursor) == result


@pytest.mark.parametrize("input,stream,pos,result", [
    (".##", [{"a": "b", "aa": "d"}], (1, 1), [Token(""), Field("a"), Field("aa")]),
    (".a##", [{"a": "b", "aa": "d"}], (1, 2), [Field("a"), Field("aa")]),
    ("(.##", [{"a": "b", "aa": "d"}], (2, 2), [Token(""), Field("a"), Field("aa")]),
    (".a.##", [{"a": {"b": "c", "bb": "d"}}], (3, 3), [Field("b"), Field("bb")]),
    (".a.b##", [{"a": {"b": "c", "bb": "d"}}], (3, 4), [Field("b"), Field("bb")]),
    (".a|.##", [{"a": {"b": "c", "bb": "d"}}], (4, 4), [Token(""), Field("b"), Field("bb")]),
    (".a|.b##", [{"a": {"b": "c", "bb": "d"}}], (4, 5), [Field("b"), Field("bb")]),
    (".##", [{"a":"b", "aa": "bb", "b": "c", "bb": {"d": "dd", "e": "ee"}}], (1, 1),
        [Token(""), Field("a"), Field("aa"), Field("b"), Field("bb")]),
    (".a##", [{"a": "b", "aa": "bb", "b": "c", "bb": {"d": "dd", "e": "ee"}}], (1, 2),
        [Field("a"), Field("aa")]),
    (".aa##", [{"a": "b", "aa": "bb", "b": "c", "bb": {"d": "dd", "e": "ee"}}], (1, 3),
        [Field("aa")]),
    (".aaa##", [{"a": "b", "aa": "bb", "b": "c", "bb": {"d": "dd", "e": "ee"}}], (1, 4),
        []),
    (".b##", [{"a": "b", "aa": "bb", "b": "c", "bb": {"d": "dd", "e": "ee"}}], (1, 2),
        [Field("b"), Field("bb")]),
    (".bb##", [{"a": "b", "aa": "bb", "b": "c", "bb": {"d": "dd", "e": "ee"}}], (1, 3),
     [Field("bb")]),
    (".bb.##", [{"a": "b", "aa": "bb", "b": "c", "bb": {"d": "dd", "e": "ee"}}], (4, 4),
     [Field("d"), Field("e")]),
    (".bb.d##", [{"a": "b", "aa": "bb", "b": "c", "bb": {"d": "dd", "e": "ee"}}], (4, 5),
     [Field("d")]),
    (". ##", [{"a": "b", "aa": "d"}], (1, 1), [Token(""), Field("a"), Field("aa")]),
    ('."##', [{"a": "b", "aa": "d"}], (1, 2), [Field("a"), Field("aa")]),
    ('."a"."##', [{"a": {"aaa": "b", "aa": "d"}}], (5, 6), [Field("aa"), Field("aaa")]),
], ids=simplify)
def test_completion(input, stream, pos, result):
    # Work out where the cursor is in the input
    cursor = input.index("##")
    input = input[:cursor] + input[cursor + 2:]

    if isinstance(result, type) and issubclass(result, Exception):
        with pytest.raises(result):
            completer(input, cursor)
        return
    assert completer(input, cursor)(stream) == (result, pos)
