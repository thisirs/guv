class Operation:
    """Base class for operation to apply to `effectif.xlsx`."""

    def message(self):
        return "Pas de message"

    @property
    def deps(self):
        return []

    def apply(self, df):
        pass
