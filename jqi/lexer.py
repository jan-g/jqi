from parsy import generate, regex, string_from, match_item, Parser, Result, eof, seq
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


class String(Str):
    pass


class PartialString(Str):
    pass


ws = regex(r'[ \t\n]+').map(WS)
comment = regex(r'#[^\r\n]*').map(WS)
IDENT = regex(r'([a-zA-Z_][a-zA-Z_0-9]*::)*[a-zA-Z_][a-zA-Z_0-9]*').map(Ident)
FIELD = regex(r'\.[a-zA-Z_][a-zA-Z_0-9]*').map(lambda f: Field(f[1:]))
LITERAL = regex(r'-?[0-9]+').map(int) | regex(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?').map(float)
FORMAT = regex(r'@[a-zA-Z0-9_]+').map(Format)
JSON_STRING_REGEX= r'(\\(["\\\/bfnrt]|u[a-fA-F0-9]{4})|[^"\\\0-\x1F\x7F]+)*'
QQString = regex(rf'"{JSON_STRING_REGEX}"').map(loads).map(String)
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
        closer = yield match_item(close) | eof
        if closer is None:
            return Token(open), *lexes
        return Token(open), *lexes, Token(close)
    return _


bracket = _bracket("[", "]")
brace = _bracket("{", "}")
paren = _bracket("(", ")")


class Cursor:
    class CursorToken(Str):
        pass

    CURSOR = CursorToken("#CURSOR#")

    def __init__(self, offset=None):
        self.offset = offset
        self.cursor_reported = False

    @property
    def check_cursor(self):
        @Parser
        def check_cursor(stream, index):
            if self.offset is not None and index >= self.offset and not self.cursor_reported:
                self.cursor_reported = True
                return Result.success(len(stream), Cursor.CURSOR)
            return Result.failure(index, "cursor")
        return check_cursor


def flatten(xs):
    if isinstance(xs, list) or isinstance(xs, tuple):
        result = []
        for x in xs:
            result.extend(flatten(x))
        return result
    return [xs]


_lexer = ((ws | comment | FIELD | LITERAL | FORMAT | QQString | token | IDENT | bracket | brace | paren)
          .many()
          .map(flatten)
          .map(lambda l: [i for i in l if not isinstance(i, WS)]))

lexer = _lexer


def lex(s, offset=None):
    # For the moment: not re-entrant!
    global lexer
    if offset is not None:
        cursor = Cursor(offset)
        Q_String = seq(regex(rf'"{JSON_STRING_REGEX}').map(lambda s: PartialString(loads(s + '"'))),
                       cursor.check_cursor)

        lexer = ((cursor.check_cursor |
                  ws | comment | FIELD | LITERAL | FORMAT | QQString | Q_String | token | IDENT | bracket | brace | paren)
                 .many()
                 .map(flatten)
                 .map(lambda l: [i for i in l if not isinstance(i, WS)]))
    else:
        lexer = _lexer
    return lexer.parse(s)
