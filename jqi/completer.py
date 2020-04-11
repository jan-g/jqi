from .parser import Field, Token, Ident, PartialString


class Completion(Exception):
    def __init__(self, completions=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.completions = completions


# return the union of keys of objects in the stream
def sample_objects(stream):
    keys = set()
    for item in stream:
        try:
            keys.update(item.keys())
        except AttributeError:
            pass
    return sorted(keys)


def complete_term(term, evaluator):
    if term == Token("."):
        def complete_term(env, stream):
            samples = sample_objects(stream)
            raise Completion(completions=[Token(".")] + [Field(k) for k in samples])
        return complete_term
    elif isinstance(term, (Field, PartialString)):
        def complete_term(env, stream):
            samples = sample_objects(stream)
            raise Completion(completions=[Field(k) for k in samples if k.startswith(term)])
        return complete_term
    else:
        return evaluator


def complete_field(prefix, evaluator):
    def complete_field(env, stream):
        _, stream = evaluator(env, stream)
        samples = sample_objects(stream)
        raise Completion(completions=[Field(k) for k in samples if k.startswith(prefix)])
    return complete_field
