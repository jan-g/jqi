"""
A subset of the jq grammar
"""
from parsy import generate, regex, string_from, match_item, test_item, seq
from .lexer import lexer, Token, Ident, Field, Str

"""
Combiner for the following:

%precedence FUNCDEF
%right '|'
%left ','
%right "//"
%nonassoc '=' SETPIPE SETPLUS SETMINUS SETMULT SETDIV SETMOD SETDEFINEDOR
%left OR
%left AND
%nonassoc NEQ EQ '<' '>' LESSEQ GREATEREQ
%left '+' '-'
%left '*' '/' '%'
%precedence NONOPT /* non-optional; rules for which a specialized
                      '?' rule should be preferred over Exp '?' */
%precedence '?'
%precedence "try"
%precedence "catch"
"""
def chainl(item, op):
    @generate
    def _():
        sum = yield item
        while True:
            next = yield (seq(op, item)).optional()
            if next is None:
                break
            (combiner, other) = next
            sum = combiner(sum, other)

        return sum
    return _


def chainr(item, op):
    @generate
    def _():
        sum = yield item
        rhs = yield (seq(op, _)).optional()
        if rhs is not None:
            (combiner, other) = rhs
            sum = combiner(sum, other)
        return sum
    return _


def token(t):
    return match_item(Token(t))


def match_type(t, description=None):
    def _(i):
        return isinstance(i, t)
    return test_item(_, description=description)
    return test_item(lambda i: isinstance(i, t), description=description)


# field = match_type(Field, "Field")
@generate
def field():
    f = yield match_type(Field, "Field")
    return f


def _dot(env, stream):
    return env, stream


class Error(Str):
    @staticmethod
    def from_exception(e):
        return Error(str(e))

    def __eq__(self, other):
        return other is Error


def _field(f):
    def access(i):
        try:
            return i[str(f)]
        except Exception as e:
            return Error.from_exception(e)

    def _field_access(env, stream):
        return env, [access(i) for i in stream]

    return _field_access


@generate
def term():
    t = yield (
        token(".").result(_dot) |
        field.map(_field)
    )
    return t


"""
        '.'   |
        ".."  |
        LITERAL  |
        String   |
        FORMAT   |
        "break" '$' IDENT    |
        '.' String           |
        '.' String '?'       |
        FIELD                |
        FIELD '?'            |
        IDENT                |
        IDENT '(' Args ')'   |
        '(' Exp ')'     |
        '[' Exp ']'     |
        '[' ']'         |
        '{' MkDict '}'  |
        '$' "__loc__"   |
        '$' IDENT       |
        Term FIELD           |
        Term FIELD '?'       |
        Term '.' String      |
        Term '.' String '?'  |
        Term '[' ']'                  |
        Term '[' ']' '?'              |
        Term '[' Exp ']'              |
        Term '[' Exp ']' '?'          |
        Term '[' Exp ':' ']'          |
        Term '[' Exp ':' ']' '?'      |
        Term '[' ':' Exp ']'          |
        Term '[' ':' Exp ']' '?'      |
        Term '[' Exp ':' Exp ']'      |
        Term '[' Exp ':' Exp ']' '?'  |
"""


@generate
def _bar():
    yield token("|")

    def _(x, y):
        def pipe(env, stream):
            env, stream = x(env, stream)
            return y(env, stream)
        return pipe

    return _


exp1 = chainr(term, _bar)

"""
%right '|'
%left ','

"""

exp = exp1
"""
%precedence FUNCDEF
%right '|'
%left ','
%right "//"
%nonassoc '=' SETPIPE SETPLUS SETMINUS SETMULT SETDIV SETMOD SETDEFINEDOR
%left OR
%left AND
%nonassoc NEQ EQ '<' '>' LESSEQ GREATEREQ
%left '+' '-'
%left '*' '/' '%'
%precedence NONOPT /* non-optional; rules for which a specialized
                      '?' rule should be preferred over Exp '?' */
%precedence '?'
%precedence "try"
%precedence "catch"
"""


def parse(s, start=exp):
    return start.parse(lexer.parse(s))
