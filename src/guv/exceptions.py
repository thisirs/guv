class DependentTaskParserError(Exception):
    pass


class ImproperlyConfigured(Exception):
    pass


class NotUVDirectory(Exception):
    pass


class AbortWithBody(Exception):
    pass


class ImpossibleMerge(Exception):
    pass


class CommonColumns(Exception):
    def __init__(self, common_columns, origin=None):
        self.common_columns = common_columns
        self.origin = origin

    def __str__(self):
        s = "s" if len(self.common_columns) > 1 else ""
        common_cols = ", ".join(f"`{e}`" for e in self.common_columns)
        if self.origin is None:
            return f"Colonne{s} déjà existante{s}: {common_cols}"
        else:
            return f"Colonne{s} déjà existante{s}: {common_cols} dans le dataframe issu du fichier `{self.origin}"
