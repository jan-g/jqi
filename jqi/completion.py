from .lexer import lex
from .parser import top_level
from .completer import *
from .eval import make_env, splice


def completer(s, offset, start=top_level):
    evaluator = start.parse(lex(s, offset))

    def complete(stream="", env=None):
        if env is None:
            env = {}
        env = make_env().update(env)    # Install standard bindings
        try:
            _ = evaluator(splice(env, stream))
            return []
        except Completion as c:
            return c.completions, c.pos if c.pos is not None else (offset, offset)

    return complete
