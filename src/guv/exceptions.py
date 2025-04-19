class DependentTaskParserError(Exception):
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


class MissingColumns(Exception):
    def __init__(self, missing_columns, available_columns, origin=None):
        self.missing_columns = missing_columns
        self.available_columns = available_columns
        self.origin = origin

    def __str__(self):
        s = "s" if len(self.missing_columns) > 1 else ""
        missing_cols = ", ".join(f"`{e}`" for e in self.missing_columns)
        avail_cols = ", ".join(f"`{e}`" for e in self.available_columns)
        if self.origin is None:
            return f"Colonne{s} manquante{s}: {missing_cols}. Colonnes disponibles: {avail_cols}"
        else:
            return f"Colonne{s} manquante{s}: {missing_cols} dans le dataframe issu du fichier `{self.origin}`. Colonnes disponibles: {avail_cols}"


class GuvUserError(Exception):
    pass


class CliArgumentError(GuvUserError):
    pass


class ImproperlyConfigured(GuvUserError):
    pass


class FileNotFoundError(GuvUserError):
    pass
