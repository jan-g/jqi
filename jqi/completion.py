from .lexer import lex
from .parser import exp
from .completer import *


def complete(s, offset, start=exp):
    evaluator = start.parse(lex(s, offset))

    def complete(env, stream):
        try:
            _, _ = evaluator(env, stream)
            return []
        except Completion as c:
            return c.completions

    return complete
