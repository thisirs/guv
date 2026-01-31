import copy
import functools
import importlib.metadata
import os
from pathlib import Path
import re
import textwrap
from collections.abc import Callable
from datetime import timedelta
from typing import List, Literal, Optional, Union

import numpy as np
import pandas as pd

from .aggregator import Aggregator, ColumnsMerger
from .config import settings
from .exceptions import GuvUserError, ImproperlyConfigured
from .logger import logger
from .operation import Operation
from .tasks.internal import Documents
from .translations import _, Docstring
from .utils import (check_if_absent, check_if_present, convert_to_numeric,
                    read_dataframe, slugrot_string)
from .utils_config import check_filename, rel_to_dir


def slugrot(df, *columns):
    "Rotation-invariant hash function on a dataframe"

    check_if_present(df, columns)
    s = df[list(columns)].apply(
        lambda x: "".join(x.astype(str)),
        axis=1
    )

    s = s.apply(slugrot_string)
    s.name = "guv_" + "_".join(columns)
    return s


class SlugRotMerger(ColumnsMerger):
    def __init__(self, *columns, type=None):
        super().__init__(*columns, type=type, func=slugrot)


def id_slug(*columns):
    return SlugRotMerger(*columns)


def make_concat(df, *columns):
    check_if_present(df, columns)
    s = df[list(columns)].apply(
        lambda x: "".join(x.astype(str)),
        axis=1
    )

    s.name = "guv_" + "_".join(columns)
    return s


def concat(*columns):
    return ColumnsMerger(*columns, func=make_concat)


class FillnaColumn(Operation):
    __doc__ = Docstring()

    hash_fields = ["colname", "na_value", "group_column"]

    def __init__(
        self,
        colname: str,
        *,
        na_value: Optional[str] = None,
        group_column: Optional[str] = None
    ):
        super().__init__()
        self.colname = colname
        self.na_value = na_value
        self.group_column = group_column

    def apply(self, df):
        if not((self.na_value is None) ^ (self.group_column is None)):
            raise ImproperlyConfigured(_("Only one of the options `na_value` and `group_column` must be specified"))

        if self.na_value is not None:
            check_if_present(df, self.colname)
            with pd.option_context('mode.chained_assignment', None):
                df.loc[:, self.colname] = df[self.colname].fillna(self.na_value)
        else:
            def fill_by_group(g):
                if not isinstance(g.name, str):
                    logger.warning(_("The column `%s` contains empty entries"), self.group_column)
                    return g

                valid = g[self.colname].dropna()

                if len(valid) == 0:
                    logger.warning(_("No non-NA value in the group `%s`"), g.name)
                elif len(valid) == 1:
                    g[self.colname] = valid.iloc[0]
                else:
                    all_equal = (valid == valid.iloc[0]).all()
                    if all_equal:
                        g[self.colname] = valid.iloc[0]
                    else:
                        logger.warning(_("Multiple non-NA and different values in the group `%s`"), g.name)

                return g

            check_if_present(df, [self.colname, self.group_column])
            df = df.groupby(self.group_column, dropna=False, group_keys=False)[df.columns].apply(fill_by_group, include_groups=True)

        return df

    def message(self):
        if self.na_value is not None:
            return _("Replace NAs in the column `{colname}` with the value `{na_value}`").format(colname=self.colname, na_value=self.na_value)

        return _("Replace NAs in the column `{colname}` by grouping by `{group_column}`").format(colname=self.colname, group_column=self.group_column)


class ReplaceRegex(Operation):
    __doc__ = Docstring()

    hash_fields = ["colname", "reps", "new_colname", "backup"]

    def __init__(
        self,
        colname: str,
        *reps,
        new_colname: Optional[str] = None,
        backup: Optional[bool] = False,
        msg: Optional[str] = None,
    ):
        super().__init__()
        self.colname = colname
        self.reps = reps
        self.new_colname = new_colname
        self.backup = backup
        self.msg = msg

    def apply(self, df):
        if self.backup is True and self.new_colname is not None:
            raise ImproperlyConfigured(
                _("The arguments `backup` and `new_colname` are incompatible.")
            )

        check_if_present(df, self.colname)

        new_column = df[self.colname].copy()
        for rep in self.reps:
            new_column = new_column.str.replace(*rep, regex=True)

        return replace_column_aux(
            df,
            new_colname=self.new_colname,
            colname=self.colname,
            new_column=new_column,
            backup=self.backup,
        )

    def message(self):
        if self.msg is not None:
            return self.msg
        if self.new_colname is None:
            return _("Regex replacement in column `{colname}`").format(colname=self.colname)

        return _("Regex replacement in column `{colname}` to column `{new_colname}`").format(colname=self.colname, new_colname=self.new_colname)


class ReplaceColumn(Operation):
    __doc__ = Docstring()

    hash_fields = ["colname", "rep_dict", "new_colname", "backup"]

    def __init__(
        self,
        colname: str,
        rep_dict: dict,
        new_colname: Optional[str] = None,
        backup: Optional[bool] = False,
        msg: Optional[str] = None,
    ):
        super().__init__()
        self.colname = colname
        self.rep_dict = rep_dict
        self.new_colname = new_colname
        self.backup = backup
        self.msg = msg

    def apply(self, df):
        if self.backup is True and self.new_colname is not None:
            raise ImproperlyConfigured(
                _("The arguments `backup` and `new_colname` are incompatible.")
            )

        check_if_present(df, self.colname)
        new_column = df[self.colname].replace(self.rep_dict)
        return replace_column_aux(
            df,
            new_colname=self.new_colname,
            colname=self.colname,
            new_column=new_column,
            backup=self.backup,
        )

    def message(self):
        if self.msg is not None:
            return self.msg
        if self.new_colname is None:
            return _("Replacement in column `{colname}`").format(colname=self.colname)

        return _("Replacement in column `{colname}` to column `{new_colname}`").format(colname=self.colname, new_colname=self.new_colname)


class ApplyDf(Operation):
    __doc__ = Docstring()

    hash_fields = ["func"]

    def __init__(self, func: Callable, msg: Optional[str] = None):
        super().__init__()
        self.func = func
        self.msg = msg

    def apply(self, df):
        return self.func(df)

    def message(self):
        if self.msg is not None:
            return self.msg

        return _("Apply a function to the Dataframe")


class ApplyColumn(Operation):
    __doc__ = Docstring()

    hash_fields = ["colname", "func"]

    def __init__(self, colname: str, func: Callable, msg: Optional[str] = None):
        super().__init__()
        self.colname = colname
        self.func = func
        self.msg = msg

    def apply(self, df):
        check_if_present(df, self.colname)
        df.loc[:, self.colname] = df[self.colname].apply(self.func)
        return df

    def message(self):
        if self.msg is not None:
            return self.msg

        return _("Apply a function to the column `{colname}`").format(colname=self.colname)


class ComputeNewColumn(Operation):
    __doc__ = Docstring()

    hash_fields = ["cols", "func", "colname"]

    def __init__(self, *cols: str, func: Callable, colname: str, msg: Optional[str] = None):
        super().__init__()
        self.col2id = {}
        self.cols = cols
        for col in cols:
            if isinstance(col, tuple):
                self.col2id[col[1]] = col[0]
            else:
                self.col2id[col] = col
        self.func = func
        self.colname = colname
        self.msg = msg

    def apply(self, df):
        check_if_present(df, self.col2id.keys())
        check_if_absent(df, self.colname, errors="warning")

        def compute_value(row):
            # Extract values from row and rename
            values = row.loc[list(self.col2id.keys())]
            values = values.rename(index=self.col2id)

            return self.func(values)

        new_col = df.apply(compute_value, axis=1)
        df = df.assign(**{self.colname: new_col})
        return df

    def message(self):
        if self.msg is not None:
            return self.msg

        return _("Calculation of the column `{colname}`").format(colname=self.colname)


class ApplyCell(Operation):
    __doc__ = Docstring()

    hash_fields = ["name_or_email", "colname", "value"]

    def __init__(self, name_or_email: str, colname: str, value, msg: Optional[str] = None):
        super().__init__()
        self.name_or_email = name_or_email
        self.colname = colname
        self.value = value
        self.msg = msg

    def apply(self, df):
        check_if_present(df, [self.colname, self.settings.EMAIL_COLUMN])
        left_on = self.settings.EMAIL_COLUMN

        if '@' in self.name_or_email:
            sturow = df.loc[df[left_on] == self.name_or_email]
            if len(sturow) > 1:
                raise GuvUserError(_("Email address `{email}` appears multiple times").format(email=self.name_or_email))
            if len(sturow) == 0:
                raise GuvUserError(_("Email address `{email}` not present in the central file").format(email=self.name_or_email))
            stuidx = sturow.index[0]
        else:
            # Add slugname column
            check_if_absent(df, "fullname_slug")
            columns = [self.settings.LASTNAME_COLUMN, self.settings.NAME_COLUMN]
            df["fullname_slug"] = slugrot(df, *columns)

            sturow = df.loc[df.fullname_slug == slugrot_string(self.name_or_email)]
            if len(sturow) > 1:
                raise GuvUserError(_("Student named `{name}` appears multiple times").format(name=self.name_or_email))
            if len(sturow) == 0:
                raise GuvUserError(_("Student named `{name}` not present or recognized in the central file").format(name=self.name_or_email))
            stuidx = sturow.index[0]
            df = df.drop('fullname_slug', axis=1)

        df.loc[stuidx, self.colname] = self.value

        return df

    def message(self):
        if self.msg is not None:
            return self.msg

        return _("Modification of the column `{colname}` for the identifier `{name_or_email}`").format(colname=self.colname, name_or_email=self.name_or_email)


class FileOperation(Operation):
    hash_fields = ["_filename"]

    def __init__(self, filename):
        super().__init__()
        self._filename = filename

    @property
    def filename(self):
        return str(Path(self.base_dir) / self._filename)

    @property
    def deps(self):
        return [self.filename]

    def message(self):
        return _("Aggregation of the file `{filename}`").format(filename=rel_to_dir(self.filename, self.settings.CWD))


class Add(FileOperation):
    __doc__ = Docstring()

    hash_fields = ["_filename", "func", "kw_func"]

    def __init__(self, filename, func=None, kw_func=None):
        super().__init__(filename)
        self.func = func
        self.kw_func = kw_func

    def apply(self, df):
        if df is not None and self.func is None:
            raise ImproperlyConfigured(_("An aggregation function must be provided"))

        if df is None and self.func is not None:
            logger.warning(_("No pre-existing dataframe, the provided function is ignored"))

        if self.func is not None and df is not None:
            return self.func(df, self.filename, **self.kw_func)
        else:
            return read_dataframe(self.filename, kw_read=self.kw_func)


class Aggregate(FileOperation):
    __doc__ = Docstring()

    hash_fields = ["_filename", "left_on", "right_on", "on", "subset", "drop", "rename", "merge_policy", "preprocessing", "postprocessing", "read_method", "kw_read"]

    def __init__(
        self,
        filename: str,
        *,
        left_on: Union[None, str, callable] = None,
        right_on: Union[None, str, callable] = None,
        on: Optional[str] = None,
        subset: Union[None, str, List[str]] = None,
        drop: Union[None, str, List[str]] = None,
        rename: Optional[dict] = None,
        merge_policy: Optional[Literal["merge", "keep", "erase", "replace", "fill_na"]] = "merge",
        preprocessing: Union[None, Callable, Operation] = None,
        postprocessing: Union[None, Callable, Operation] = None,
        read_method: Optional[Callable] = None,
        kw_read: Optional[dict] = {}
    ):
        super().__init__(filename)
        self._filename = filename
        self.left_on = left_on
        self.right_on = right_on
        self.on = on
        self.subset = subset
        self.drop = drop
        self.rename = rename
        self.merge_policy = merge_policy
        self.preprocessing = preprocessing
        self.postprocessing = postprocessing
        self.read_method = read_method
        self.kw_read = kw_read

    def apply(self, left_df):
        right_df = read_dataframe(self.filename, kw_read=self.kw_read, read_method=self.read_method)

        if self.on is not None:
            if self.left_on is not None or self.right_on is not None:
                raise ImproperlyConfigured(_("Either `on`, or `left_on` and `right_on` must be specified."))

            left_on = self.on
            right_on = copy.copy(self.on) # Duplicate because left_on and right_on must be different
        else:
            left_on = self.left_on
            right_on = self.right_on

        # Warn if only one of left_on right_on is id_slug
        if isinstance(left_on, SlugRotMerger) ^ isinstance(right_on, SlugRotMerger):
            logger.warning(_("`left_on` and `right_on` must both be from `id_slug`"))

        agg = Aggregator(
            left_df,
            right_df,
            left_on=left_on,
            right_on=right_on,
            preprocessing=self.preprocessing,
            postprocessing=self.postprocessing,
            subset=self.subset,
            drop=self.drop,
            rename=self.rename,
            how="left",
            merge_policy=self.merge_policy
        )

        df_merge = agg.merge()
        agg.report()

        return df_merge


class AggregateSelf(Operation):
    __doc__ = Docstring()

    hash_fields = ["columns"]

    def __init__(self, *columns):
        super().__init__()
        self.columns = list(columns)

    def apply(self, left_df):
        from .tasks.internal import XlsStudentData  # Circular deps
        uv = self.info["uv"]
        right_df = XlsStudentData.read_target(XlsStudentData.target_from(uv=uv))

        login_col = self.settings.LOGIN_COLUMN
        if login_col in left_df and login_col in right_df:
            id_cols = [login_col]
            left_on = right_on = login_col
        else:
            names = [self.settings.NAME_COLUMN, self.settings.LASTNAME_COLUMN]
            names_set = set(names)
            if names_set.issubset(set(left_df.columns)) and names_set.issubset(set(right_df.columns)):
                id_cols = names
                left_on = id_slug(*names)
                right_on = id_slug(*names)
            else:
                raise GuvUserError(_("The `{login_col}` column or the `{lastname_column}` and `{name_column}` columns are required").format(
                    login_col=login_col,
                    lastname_column=self.settings.LASTNAME_COLUMN,
                    name_column=self.settings.NAME_COLUMN,
                ))

        agg = Aggregator(
            left_df,
            right_df,
            left_on=left_on,
            right_on=right_on,
            subset=list(self.columns),
            how="left",
            merge_policy="erase"
        )
        merge = agg.merge()

        # Backup manually added columns
        df = right_df[id_cols + self.columns]
        filename = str(Path(self.settings.UV_DIR) / "generated" / ".aggregate_self.xlsx")
        df.to_excel(filename, index=False)

        return merge

    def message(self):
        msg = ", ".join(f"`{e}`" for e in self.columns)
        return _("Add manual columns: {msg}").format(msg=msg)


class AggregateOrg(FileOperation):
    __doc__ = Docstring()

    hash_fields = ["_filename", "colname", "on", "postprocessing"]

    def __init__(
        self,
        filename: str,
        colname: str,
        on: Optional[str] = None,
        postprocessing: Union[None, Callable, Operation] = None,
    ):
        super().__init__(filename)
        self._filename = filename
        self.colname = colname
        self.on = on
        self.postprocessing = postprocessing

    def apply(self, left_df):
        check_filename(self.filename, base_dir=settings.SEMESTER_DIR)

        def parse_org(text):
            for chunk in re.split("^\\* *", text, flags=re.MULTILINE)[1:]:
                if not chunk:
                    continue
                header, *text = chunk.split("\n", maxsplit=1)
                text = "\n".join(text).strip("\n")
                text = textwrap.dedent(text)
                logger.debug("Header line: %s", header)
                yield header, text

        text = open(self.filename, 'r').read()
        df_org = pd.DataFrame(parse_org(text), columns=["header", self.colname])

        if self.on is None:
            columns = [self.settings.LASTNAME_COLUMN, self.settings.NAME_COLUMN]
            left_on = id_slug(*columns)
            right_on = id_slug("header")
        else:
            left_on = self.on
            right_on = "header"

        agg = Aggregator(
            left_df,
            df_org,
            left_on=left_on,
            right_on=right_on,
            postprocessing=self.postprocessing,
            how="left"
        )

        df_merge = agg.merge()
        agg.report()

        return df_merge


class FileStringOperation(FileOperation):
    msg_file = _("Aggregation of the file `{filename}`")
    msg_string = _("Direct aggregation of `{string}`")

    def __init__(self, filename_or_string):
        super().__init__(filename_or_string)
        self.filename_or_string = filename_or_string
        self._is_file = None

    @property
    def is_file(self):
        if self._is_file is None:
            # Heuristic to decide whether `filename_or_string` is a file or
            # string
            self._is_file = (
                "\n" not in self.filename_or_string
                and "---" not in self.filename_or_string
                and "*" not in self.filename_or_string
            )

        return self._is_file

    @property
    def lines(self):
        if self.is_file:
            filename = str(Path(self.base_dir) / self.filename_or_string)
            check_filename(filename, base_dir=self.base_dir)
            lines = open(filename, "r").readlines()
        else:
            lines = self.filename_or_string.splitlines(keepends=True)

        return lines

    @property
    def deps(self):
        if self.is_file:
            return [self.filename_or_string]
        else:
            return []

    def message(self):
        if self.is_file:
            return self.msg_file.format(filename=rel_to_dir(self.filename_or_string, self.settings.CWD))
        else:
            return self.msg_string.format(string=self.filename_or_string.lstrip().splitlines()[0] + "...")


class Flag(FileStringOperation):
    __doc__ = Docstring()

    hash_fields = ["_filename", "colname", "flags"]

    def __init__(self, filename_or_string: str, *, colname: str, flags: Optional[List[str]] = ["Oui", ""]):
        super().__init__(filename_or_string)
        self.colname = colname
        self.flags = flags

    def apply(self, df):
        check_if_absent(df, self.colname)

        df[self.colname] = self.flags[1]

        names = [self.settings.NAME_COLUMN, self.settings.LASTNAME_COLUMN]
        if not set(names).issubset(df):
            raise ImproperlyConfigured(_("Columns `{name_col}` and `{lastname_col}` are required").format(
                name_col=self.settings.NAME_COLUMN,
                lastname_col=self.settings.LASTNAME_COLUMN
            ))

        # Add column that acts as a primary key
        df["fullname_slug"] = slugrot(df, *names)

        for line in self.lines:
            # Saute commentaire ou ligne vide
            line = line.strip()
            if line.startswith('#'):
                continue
            if not line:
                continue

            slugname = slugrot_string(line)

            res = df.loc[df.fullname_slug == slugname]
            if len(res) == 0:
                raise GuvUserError(_("No match for `{:s}`").format(line))
            if len(res) > 1:
                raise GuvUserError(_("Multiple matches for `{:s}`").format(line))
            df.loc[res.index[0], self.colname] = self.flags[0]

        df = df.drop('fullname_slug', axis=1)
        return df


class Switch(FileStringOperation):
    __doc__ = Docstring()

    msg_file = _("Aggregation of the exchange file `{filename}`")
    msg_string = _("Direct aggregation of exchanges `{string}`")
    hash_fields = ["_filename", "colname", "backup", "new_colname"]

    def __init__(
        self,
        filename_or_string: str,
        *,
        colname: str,
        backup: bool = False,
        new_colname: Optional[str] = None,
    ):
        super().__init__(filename_or_string)
        self.colname = colname
        self.backup = backup
        self.new_colname = new_colname

    def apply(self, df):
        if self.backup is True and self.new_colname is not None:
            raise ImproperlyConfigured(
                _("The arguments `backup` and `new_colname` are incompatible.")
            )

        # Check that column exist
        check_if_present(df, self.colname)

        # Add slugname column
        check_if_absent(df, "fullname_slug")
        columns = [self.settings.LASTNAME_COLUMN, self.settings.NAME_COLUMN]
        df["fullname_slug"] = slugrot(df, *columns)

        check_if_present(df, self.settings.EMAIL_COLUMN)
        email_column = self.settings.EMAIL_COLUMN
        new_column = swap_column(df, self.lines, self.colname, email_column)
        df = replace_column_aux(
            df,
            colname=self.colname,
            new_colname=self.new_colname,
            new_column=new_column,
            backup=self.backup,
            errors="silent"
        )

        df = df.drop('fullname_slug', axis=1)
        return df


def replace_column_aux(
        df, new_colname=None, colname=None, new_column=None, backup=False, errors="warning"
):
    """Helper function for `replace_regex` and `replace_column`."""

    if backup:
        check_if_absent(df, f"{colname}_orig", errors="warning")
        df = df.assign(**{f"{colname}_orig": df[colname]})
        target_colname = colname
    elif new_colname is not None:
        target_colname = new_colname
    else:
        target_colname = colname

    check_if_absent(df, target_colname, errors=errors)
    df = df.assign(**{target_colname: new_column})

    return df


def read_pairs(lines):
    """Generate pairs read in `lines`. """

    for line in lines:
        if line.strip().startswith("#"):
            continue
        if not line.strip():
            continue
        try:
            parts = [e.strip() for e in line.split("---")]
            stu1, stu2 = parts
            if not stu1 or not stu2:
                raise GuvUserError(_("Incorrect line: `{line}`. Expected format `etu1 --- etu2`.").format(line=line.strip()))
            yield stu1, stu2
        except ValueError:
            raise GuvUserError(_("Incorrect line: `{line}`. Expected format `etu1 --- etu2`.").format(line=line.strip()))


def validate_pair(df, colname, part1, part2, email_column):
    """Return action to do with a pair `part1`, `part2`."""

    names = df[colname].unique()

    # Indice de l'étudiant 1
    if "@" in part1:
        stu1row = df.loc[df[email_column] == part1]
        if len(stu1row) != 1:
            raise GuvUserError(
                _("Email address `{email}` not present in the central file").format(email=part1)
            )
        stu1idx = stu1row.index[0]
    else:
        stu1row = df.loc[df.fullname_slug == slugrot_string(part1)]
        if len(stu1row) != 1:
            raise GuvUserError(
                _("Student named `{name}` not present or recognized in the central file").format(name=part1)
            )
        stu1idx = stu1row.index[0]

    if part2 in names:  # Le deuxième élément est une colonne
        return "move", stu1idx, part2
    elif part2 in ["null", "nan"]:
        return "quit", stu1idx, None
    elif "@" in part2:  # Le deuxième élément est une adresse email
        stu2row = df.loc[df[email_column] == part2]
        if len(stu2row) != 1:
            raise GuvUserError(
                _("Email address `{email}` not present in the central file").format(email=part2)
            )
        stu2idx = stu2row.index[0]
        return "swap", stu1idx, stu2idx
    else:
        stu2row = df.loc[df.fullname_slug == slugrot_string(part2)]
        if len(stu2row) != 1:
            raise GuvUserError(
                _("Student named `{name}` not present or recognized in the central file").format(name=part2)
            )
        stu2idx = stu2row.index[0]
        return "swap", stu1idx, stu2idx


def swap_column(df, lines, colname, email_column):
    """Return copy of column `colname` modified by swaps from `lines`. """

    new_column = df[colname].copy()

    for part1, part2 in read_pairs(lines):
        type, idx1, idx2 = validate_pair(df, colname, part1, part2, email_column)

        if type == "swap":
            logger.info(_("Exchange of `{nom1}` and `{nom2}` in the column `{colname}`").format(nom1=part1, nom2=part2, colname=colname))

            tmp = new_column[idx1]
            new_column[idx1] = new_column[idx2]
            new_column[idx2] = tmp
        elif type == "move":
            logger.info(_("Student `{nom}` assigned to group `{idx}`").format(nom=part1, idx=idx2))

            new_column[idx1] = idx2
        elif type == "quit":
            logger.info(_("Abandon student `%s`"), part1)

            new_column[idx1] = np.nan

    return new_column


class MoodleFileOperation(FileOperation):
    read_dataframe_kwargs = {}

    def __init__(self, filename):
        super().__init__(filename)
        self._moodle_df = None

    @property
    def moodle_df(self):
        if self._moodle_df is None:
            self._moodle_df = read_dataframe(self.filename, kw_read=type(self).read_dataframe_kwargs)
        return self._moodle_df


class AggregateMoodleGroups(MoodleFileOperation):
    __doc__ = Docstring()

    hash_fields = ["_filename", "colname", "backup"]

    def __init__(self, filename: str, colname: str, backup: Optional[bool] = False):
        super().__init__(filename)
        self.colname = colname
        self.backup = backup
        self._version = None

    def apply(self, df):
        # Backup column
        if self.backup:
            suffixes = ("_orig", "")
            merge_policy = "keep"
            if self.colname not in df.columns:
                logger.warning(_("The backup of the column `%s` is activated but it is not present in the central file"), self.colname)
        else:
            suffixes = ("_orig", "")
            merge_policy = "erase"

        left_on = self.settings.EMAIL_COLUMN
        right_on = self.settings.MOODLE_EMAIL_COLUMN

        # Group column is the fourth one
        group_column_name = self.moodle_df.columns[4]
        drop_columns = [v for i, v in enumerate(self.moodle_df.columns) if i != 4]
        drop_columns.remove(right_on)

        agg = Aggregator(
            df,
            self.moodle_df,
            left_on=left_on,
            right_on=right_on,
            drop=drop_columns,
            rename={group_column_name: self.colname},
            how="left",
            merge_policy=merge_policy,
            suffixes=suffixes
        )

        df_merge = agg.merge()
        agg.report()

        return df_merge

    def message(self):
        return _("Aggregation of the group file `{filename}`").format(filename=rel_to_dir(self.filename, self.settings.CWD))


class AggregateMoodleGrades(MoodleFileOperation):
    __doc__ = Docstring()

    hash_fields = ["_filename", "rename"]
    read_dataframe_kwargs = {"na_values": "-"}

    def __init__(
        self,
        filename: str,
        rename: Optional[dict] = None,
    ):
        super().__init__(filename)
        self.rename = rename

    def get_arguments(self, df):
        if df is not None:
            email_column = self.settings.EMAIL_COLUMN
            if email_column not in df.columns:
                raise ImproperlyConfigured("Email column is required to aggregate Moodle grades")
            left_on = email_column
        else:
            left_on = None

        drop = [0, 1, 2, 3, 4, len(self.moodle_df.columns)-1]

        return left_on, self.settings.MOODLE_EMAIL_COLUMN, drop

    def apply(self, left_df):
        right_df = self.moodle_df
        left_on, right_on, drop = self.get_arguments(left_df)

        right_df = right_df.drop(columns=right_df.columns[drop])


        # Convert columns into numeric if possible
        # for c in keep:
        #     try:
        #         right_df[c] = convert_to_numeric(right_df[c])
        #     except ValueError:
        #         pass

        agg = Aggregator(
            left_df,
            right_df,
            left_on=left_on,
            right_on=right_on,
            rename=self.rename,
            how="left"
        )

        df_merge = agg.merge()
        agg.report()

        return df_merge


class AggregateJury(FileOperation):
    __doc__ = Docstring()

    def __init__(self, filename: str):
        super().__init__(filename)

    def apply(self, df):
        op = Aggregate(
            self.filename,
            on=self.settings.EMAIL_COLUMN,
            subset=[_("Aggregated grade"), _("ECTS grade")]
        )
        op.setup(settings=self.settings, info=self.info)
        return op.apply(df)


def add_action_method(cls, klass, method_name):
    """Add new method named `method_name` to class `cls`"""

    @functools.wraps(klass.__init__)
    def dummy(self, *args, **kwargs):
        action = klass(*args, **kwargs)
        self.add_action(action)

    dummy.__doc__ = klass.__doc__
    dummy.__name__ = method_name

    setattr(cls, method_name, dummy)

def load_actions():
    actions = [
        ("fillna_column", FillnaColumn),
        ("replace_regex", ReplaceRegex),
        ("replace_column", ReplaceColumn),
        ("apply_df", ApplyDf),
        ("apply_column", ApplyColumn),
        ("compute_new_column", ComputeNewColumn),
        ("add", Add),
        ("aggregate", Aggregate),
        ("aggregate_self", AggregateSelf),
        ("aggregate_moodle_grades", AggregateMoodleGrades),
        ("aggregate_moodle_groups", AggregateMoodleGroups),
        ("aggregate_jury", AggregateJury),
        ("aggregate_org", AggregateOrg),
        ("flag", Flag),
        ("apply_cell", ApplyCell),
        ("switch", Switch),
    ]

    for entry_point in importlib.metadata.entry_points(group="guv_operations"):
        name = entry_point.name
        operation_class = entry_point.load()
        actions.append((name, operation_class))
    return actions


actions = load_actions()

for method_name, klass in actions:
    # Add as method
    add_action_method(Documents, klass, method_name)

    # Add as a standalone fonction
    def make_func(klass):
        def dummy(*args, **kwargs):
            return klass(*args, **kwargs)
        dummy.__doc__ = klass.__doc__
        return dummy

    globals()[method_name] = make_func(klass)


def skip_range(d1, d2):
    return [d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)]


def skip_week(d1, weeks=1):
    return [d1 + timedelta(days=x) for x in range(7*weeks-1)]
