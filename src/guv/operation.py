import re
import hashlib
import json
import random

class Operation:
    """Base class for operation to apply to `effectif.xlsx`."""

    cache = False
    hash_fields = []

    def __init__(self):
        self.base_dir = None
        self.uv = None

    def message(self):
        return "Pas de message"

    @property
    def deps(self):
        return []

    def name(self):
        return re.sub(r"(?<!^)(?<=[a-z])(?=[A-Z])", "_", type(self).__name__).lower()

    def apply(self, df):
        pass

    def fingerprint(self):
        relevant_data = {field: fingerprint(getattr(self, field)) for field in self.hash_fields}
        return json.dumps(relevant_data, sort_keys=True)

    def hash(self):
        return hashlib.sha256(self.fingerprint().encode("utf-8")).hexdigest()


def fingerprint(obj):
    if isinstance(obj, list):
        return [fingerprint(e) for e in obj]
    elif hasattr(obj, "fingerprint"):
        return obj.fingerprint()
    else:
        try:
            return json.dumps(obj, sort_keys=True)
        except TypeError:
            return random.random()
