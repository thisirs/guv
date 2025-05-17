from .translations import ngettext


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
        common_cols = ", ".join(f"`{e}`" for e in self.common_columns)
        if self.origin is None:
            return ngettext(
                "Column already exists: {common_cols}",
                "Columns already exist: {common_cols}",
                len(self.common_columns)
            ).format(common_cols=common_cols)
        else:
            return ngettext(
                "Column already exists: {common_cols} in the dataframe from the file `{origin}`",
                "Columns already exist: {common_cols} in the dataframe from the file `{origin}`",
                len(self.common_columns)
            ).format(common_cols=common_cols, origin=self.origin)


class MissingColumns(Exception):
    def __init__(self, missing_columns, available_columns, origin=None):
        self.missing_columns = missing_columns
        self.available_columns = available_columns
        self.origin = origin

    def __str__(self):
        missing_cols = ", ".join(f"`{e}`" for e in self.missing_columns)
        avail_cols = ", ".join(f"`{e}`" for e in self.available_columns)
        if self.origin is None:
            return ngettext(
                "Missing column: {missing_cols}. Available columns: {avail_cols}",
                "Missing columns: {missing_cols}. Available columns: {avail_cols}",
                len(self.missing_columns)
            ).format(missing_cols=missing_cols, avail_cols=avail_cols)
        else:
            return ngettext(
                "Missing column: {missing_cols} in the dataframe from the file `{origin}`. Available columns: {avail_cols}",
                "Missing columns: {missing_cols} in the dataframe from the file `{origin}`. Available columns: {avail_cols}",
                len(self.missing_columns)
            ).format(missing_cols=missing_cols, origin=self.origin, avail_cols=avail_cols)


class GuvUserError(Exception):
    pass


class CliArgumentError(GuvUserError):
    pass


class ImproperlyConfigured(GuvUserError):
    pass


class FileNotFoundError(GuvUserError):
    pass
