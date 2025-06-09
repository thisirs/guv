import re
import hashlib
import json
import random

class Operation:
    """Base class for operation to apply to `effectif.xlsx`."""

    cache = False
    hash_fields = []

    def __init__(self):
        self._settings = None
        self._info = None

    @property
    def settings(self):
        if self._settings is None:
            raise RuntimeError("setup() has to be called first")
        return self._settings

    @property
    def info(self):
        if self._info is None:
            raise RuntimeError("setup() has to be called first")
        return self._info

    @property
    def base_dir(self):
        return self.settings.UV_DIR

    def message(self):
        return "Pas de message"

    @property
    def deps(self):
        return []

    def name(self):
        return re.sub(r"(?<!^)(?<=[a-z])(?=[A-Z])", "_", type(self).__name__).lower()

    def apply(self, df):
        pass

    def setup(self, settings=None, info=None):
        self._settings = settings
        self._info = info

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
    elif callable(obj):
        bytecode = obj.__code__.co_code
        return hashlib.sha256(bytecode).hexdigest()
    else:
        try:
            return json.dumps(obj, sort_keys=True)
        except TypeError:
            return random.random()
