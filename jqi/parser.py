"""
A subset of the jq grammar
"""
from numbers import Number
from parsy import generate, match_item, test_item, seq, peek, ParseError, Parser, Result, index
from .lexer import lex, Token, Ident, Field, String, Cursor, PartialString
from .eval import *
from .completer import *
from .pattern import *

"""
Combiners to produce left-associative, right-associative and non-associative precedence-aware parsers.
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


def nonassoc(item1, op, item2):
    @generate
    def _():
        sum = yield item1
        rhs = yield (seq(op, item2)).optional()
        if rhs is not None:
            (combiner, other) = rhs
            sum = combiner(sum, other)
        return sum
    return _


def token(t):
    return match_item(Token(t))


def match_type(t, description=None):
    return test_item(lambda i: isinstance(i, t), description=description)


p_field = match_type(Field, "Field")
p_literal = match_type(Number, "Literal")
p_ident = match_type(Ident, "Identifier")


completion_point = peek(match_type(Cursor.CursorToken))


def at(seek):
    @Parser
    def at(stream, index):
        return Result.success(index, stream[seek])
    return at


@generate
def term():
    t = yield (
            match_type(String).map(literal) |  # String
            (token(".") >> match_type(String)).map(field) |     # . String
            (token(".") >> match_type(PartialString) << completion_point).map(field) |
            token(".").result(dot) |  # .
            p_field.map(field) |  # FIELD
            p_literal.map(literal) |               # LITERAL
            token("(") >> exp << (token(")") | completion_point.optional()) |    # ( Exp )
            p_ident.map(call) |              # IDENT
            (token("[") >> exp << token("]")).map(collect) |    # [ Exp ]
            seq(token("["), token("]")).result(literal([])) |   # [ ]
            (token("$") >> match_type(Ident)).map(variable)     # $ IDENT
    )
    while True:
        # Work out the previous token:
        idx = yield index
        prev = yield at(idx - 1)

        # Completion support. We have to inject this explicitly into the grammar
        cursor = yield completion_point.optional()
        if cursor is not None:
            # cursor detected, injecting completion capability
            return complete_term(prev, t)

        f = yield p_field.optional()          # Term FIELD
        if f is not None:
            # Complete '.a.b'
            cursor = yield completion_point.optional()
            if cursor is not None:
                # cursor detected, injecting completion capability
                return complete_field(f, t)
            t = pipe(t, field(f))
            continue

        d = yield token(".").optional()         # Term . String
        if d is not None:
            # Complete '.a.'
            c = yield completion_point.optional()
            if c is not None:
                return complete_field(Field.make((d.start, ".", d.end)), t)     # Synthesise a position

            s = yield (match_type(PartialString) << completion_point).optional()
            # Complete ' ."a '
            if s is not None:
                return complete_field(s, t)

            s = yield match_type(String)
            t = pipe(t, field(s))
            continue

        b = yield seq(token("["), token("]")).optional()    # Term [ ]
        if b is not None:
            t = pipe(t, iterate)
            continue

        break

    return t


"""
Remaining items in Term:
        ".."  |
        FORMAT   |
        "break" '$' IDENT    |
        '.' String '?'       |
        FIELD '?'            |
        IDENT '(' Args ')'   |
        '[' ']'         |
        '{' MkDict '}'  |
        '$' "__loc__"   |
        Term FIELD '?'       |
        Term '.' String '?'  |
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


def operator(t, op):
    @generate
    def _():
        yield token(t)
        return op
    return _


def TODO(t):
    @generate
    def _():
        yield token(t)
        raise NotImplementedError(t)
    return _


# Binds tightest
exp1 = chainl(term, operator("*", op_mul) | TODO("/") | TODO("%"))
exp2 = chainl(exp1, operator("+", op_add) | operator("-", op_sub))
exp3 = nonassoc(exp2, TODO("!=") | TODO("==") | TODO("<") | TODO(">") | TODO("<=") | TODO(">="), exp2)
exp4 = chainl(exp3, operator("and", log_and))
exp5 = chainl(exp4, operator("or", log_or))
exp6 = nonassoc(exp5, TODO("=") | TODO("|=") | TODO("+=") | TODO("-=") | TODO("*=") | TODO("/=") | TODO("//="), exp5)
exp7 = chainr(exp6, TODO("//"))
exp8 = chainl(exp7, operator(",", comma))
exp9 = chainr(exp8, operator("|", pipe))
# Binds loosest

@generate
def exp():
    bind = yield seq(term, token("as"), pattern, token("|"), exp).optional()
    if bind is not None:
        return binding(bind[0], bind[2], bind[4])

    e = yield exp9 << match_type(Cursor.CursorToken).optional()
    return e


@generate
def pattern():
    bare_var = yield (token("$") >> match_type(Ident)).optional()
    if bare_var is not None:
        return ValueMatch(bare_var)

    aps = yield (token("[") >> pattern.sep_by(token(",")) << token("]")).optional()
    if aps is not None:
        return ArrayMatch(*aps)

"""
Pattern:
       '$' IDENT           |
        '[' ArrayPats ']'  |
        '{' ObjPats '}' 

ArrayPats:
        Pattern  |
        ArrayPats ',' Pattern 

ObjPats:
        ObjPat  |
        ObjPats ',' ObjPat 

ObjPat:
        '$' IDENT                |      # Just as {foo} is a handy way of writing {foo: .foo}, so {$foo} is a handy way of writing {foo:$foo}
        IDENT       ':' Pattern  |
        Keyword     ':' Pattern  |
        String      ':' Pattern  |
        '(' Exp ')' ':' Pattern
"""


def parse(s, start=exp):
    return start.parse(lex(s))


def complete(s, offset, start=exp):
    return start.parse(lex(s, offset))
