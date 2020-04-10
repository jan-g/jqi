from .parser import *


def complete(s, offset, start=exp):
    return start.parse(lex(s, offset))
