from schema import Schema, And, Use


class Iterable:
    "Schema helper to validate an iterable of given schemas"

    def __init__(self, *schemas):
        self.schemas = schemas

    def validate(self, obj):
        s = Schema(
            And(
                Schema(
                    lambda x: len(x) == len(self.schemas), error="Not of same length"
                ),
                Use(lambda x: [Schema(s).validate(e) for s, e in zip(self.schemas, x)]),
            )
        )
        return s.validate(obj)
