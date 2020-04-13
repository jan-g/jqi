from parsy import generate, regex, string_from, match_item, Parser, Result, eof, seq, index
from json import loads


class Str(str):
    @classmethod
    def make(cls, start_body_end):
        (start, body, end) = start_body_end
        item = cls(body)
        item.pos = (start, end)
        return item

    @property
    def start(self):
        return self.pos[0]

    @property
    def end(self):
        return self.pos[1]

    def __eq__(self, other):
        if type(self) is type(other) or type(other) is str:
            self_pos = getattr(self, "pos", None)
            other_pos = getattr(other, "pos", None)
            return str(self) == str(other) and (self_pos is None or other_pos is None or self_pos == other_pos)
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
    @classmethod
    def make(cls, start_body_end):
        # The field name leaves out the leading '.'
        # The field position leaves out the leading '.'
        # This makes completion a little easier
        (start, body, end) = start_body_end
        item = cls(body[1:])
        item.pos = (start + 1, end)
        return item


class Format(Str):
    pass


class Token(Str):
    pass


class String(Str):
    @classmethod
    def make(cls, start_body_end):
        (start, body, end) = start_body_end
        item = cls(loads(body))
        item.pos = (start, end)
        return item


class PartialString(Str):
    @classmethod
    def make(cls, start_body_end):
        (start, body, end) = start_body_end
        item = cls(loads(body + '"'))
        item.pos = (start, end)
        return item


class Int(int):
    @classmethod
    def make(cls, start_body_end):
        (start, body, end) = start_body_end
        item = cls(body)
        item.pos = (start, end)
        return item


class Float(float):
    @classmethod
    def make(cls, start_body_end):
        (start, body, end) = start_body_end
        item = cls(body)
        item.pos = (start, end)
        return item


def mark(parser):
    @generate
    def mark():
        start = yield index
        item = yield parser
        end = yield index
        return start, item, end
    return mark


ws = regex(r'[ \t\n]+').map(WS)
comment = regex(r'#[^\r\n]*').map(WS)
IDENT = mark(regex(r'([a-zA-Z_][a-zA-Z_0-9]*::)*[a-zA-Z_][a-zA-Z_0-9]*')).map(Ident.make)
FIELD = mark(regex(r'\.[a-zA-Z_][a-zA-Z_0-9]*')).map(Field.make)
LITERAL = (mark(regex(r'-?[0-9]+')).map(Int.make) |
           mark(regex(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?')).map(Float.make))
FORMAT = mark(regex(r'@[a-zA-Z0-9_]+')).map(Format.make)
JSON_STRING_REGEX= r'(\\(["\\\/bfnrt]|u[a-fA-F0-9]{4})|[^"\\\0-\x1F\x7F]+)*'
QQString = mark(regex(rf'"{JSON_STRING_REGEX}"')).map(String.make)
token = mark(string_from(
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
    ".", "?", "=", ";", ",", ":", "|", "+", "-", "*", "/", "%", "$", "<", ">",
)).map(Token.make)


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
        Q_String = seq(mark(regex(rf'"{JSON_STRING_REGEX}')).map(PartialString.make),
                       cursor.check_cursor)

        lexer = ((cursor.check_cursor |
                  ws | comment | FIELD | LITERAL | FORMAT | QQString | Q_String | token | IDENT | bracket | brace | paren)
                 .many()
                 .map(flatten)
                 .map(lambda l: [i for i in l if not isinstance(i, WS)]))
    else:
        lexer = _lexer
    return lexer.parse(s)
