from parsy import generate, regex, string_from, match_item
from json import loads


class Str(str):
    def __eq__(self, other):
        if type(self) is type(other) or type(other) is str:
            return str(self) == str(other)
        return False

    def __ne__(self, other):
        if type(self) is type(other) or type(other) is str:
            return str(self) != str(other)
        return True

    def __repr__(self):
        return "{}({})".format(type(self).__name__, str(self))


class WS(Str):
    pass


class Ident(Str):
    pass


class Field(Str):
    pass


class Format(Str):
    pass


class Token(Str):
    pass


ws = regex(r'[ \t\n]+').map(WS)
comment = regex(r'#[^\r\n]*').map(WS)
IDENT = regex(r'([a-zA-Z_][a-zA-Z_0-9]*::)*[a-zA-Z_][a-zA-Z_0-9]*').map(Ident)
FIELD = regex(r'\.[a-zA-Z_][a-zA-Z_0-9]*').map(lambda f: Field(f[1:]))
LITERAL = regex(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?').map(float)
FORMAT = regex(r'@[a-zA-Z0-9_]+').map(Format)
QQString = regex(r'"(\\(["\\\/bfnrt]|u[a-fA-F0-9]{4})|[^"\\\0-\x1F\x7F]+)*"').map(loads)
token = string_from(
    "!=",
    "==",
    "as",
    "import",
    "include",
    "module",
    "def",
    "if", "then", "else", "elif",
    "and",
    "or",
    "end",
    "reduce",
    "foreach",
    "//",
    "try", "catch",
    "label", "break",
    "__loc__",
    "|=", "+=", "-=", "*=", "/=", "%=", "//=", "<=", ">=", "..", "?//",
    ".", "?", "=", ";", ",", ":", "|", "+", "-", "*", "/", "%", "\$", "<", ">",
).map(Token)


def _bracket(open, close):
    @generate
    def _():
        yield match_item(open)
        lexes = yield lexer
        yield match_item(close)
        return Token(open), *lexes, Token(close)
    return _


bracket = _bracket("[", "]")
brace = _bracket("{", "}")
paren = _bracket("(", ")")


def flatten(xs):
    if isinstance(xs, list) or isinstance(xs, tuple):
        result = []
        for x in xs:
            result.extend(flatten(x))
        return result
    return [xs]


lexer = ((ws | comment | IDENT | FIELD | LITERAL | FORMAT | QQString | token | bracket | brace | paren)
         .many()
         .map(flatten)
         .map(lambda l: [i for i in l if not isinstance(i, WS)]))

