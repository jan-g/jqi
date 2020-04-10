from .lexer import Str


class Error(Str):
    @staticmethod
    def from_exception(e):
        return Error(str(e))

    def __eq__(self, other):
        return other is Error
