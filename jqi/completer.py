from .parser import Field, Token, Ident, PartialString, String


class Completion(Exception):
    def __init__(self, completions=None, pos=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.completions = completions
        self.pos = pos


# return the union of keys of objects in the stream
def sample_objects(env_stream):
    keys = set()
    for _, item in env_stream:
        try:
            keys.update(item.keys())
        except AttributeError:
            pass
    return sorted(keys)


def field_name(k):
    if k.isalnum():
        return Field(k)
    else:
        return String(k)

def complete_term(term, evaluator):
    if term == Token("."):
        pos = (term.start + 1, term.end)
        def complete_term(env_stream):
            samples = sample_objects(env_stream)
            raise Completion(completions=[Token("")] + [field_name(k) for k in samples], pos=pos)
        return complete_term
    elif isinstance(term, (Field, PartialString)):
        def complete_term(env_stream):
            samples = sample_objects(env_stream)
            raise Completion(completions=[field_name(k) for k in samples if k.startswith(term)], pos=term.pos)
        return complete_term
    else:
        return evaluator


def complete_field(prefix, evaluator):
    def complete_field(env_stream):
        stream = evaluator(env_stream)
        samples = sample_objects(stream)
        raise Completion(completions=[field_name(k) for k in samples if k.startswith(prefix)], pos=prefix.pos)
    return complete_field
