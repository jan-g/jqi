import pytest
from jqi.parser import parse, Token, Field, Ident, term, exp, ParseError
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


@pytest.mark.parametrize("input,stream,result", [
    ('true', [None], [True]),
    ('false', [None], [False]),
    ('empty', [None], []),
    ('null', [None], [None]),
    ('null|not', [None], [True]),
    ('false|not', [None], [True]),
    ('1|not', [None], [False]),
    ('(true, (false, true), 1, "foo", [], {})|select(.)', [None], [True, True, 1, "foo", [], {}]),
    ('1, 2, 3 | select(. < 3, . % 2 != 0)', [None], [1, 1, 2, 3]),
], ids=simplify)
def test_func(input, stream, result):
    if isinstance(result, type) and issubclass(result, Exception):
        with pytest.raises(result):
            parse(input, start=term)
        return
    env = make_env()
    assert parse(input, start=exp)(env, stream) == (env, result)
