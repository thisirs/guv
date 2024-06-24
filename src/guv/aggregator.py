from abc import ABC, abstractmethod
import pandas as pd

from .exceptions import ImpossibleMerge
from .logger import logger
from .operation import Operation
from .utils_config import check_if_present
from .utils import ps, plural


class Merger(ABC):
    def __init__(self, type=None):
        self.type = type

    @staticmethod
    def from_obj(obj, type=None):
        if isinstance(obj, str):
            return SimpleMerger(obj, type=type)
        elif isinstance(obj, Merger):
            obj.type = type
            return obj
        else:
            raise Exception("Unknown merger")

    @property
    def index_column(self):
        """Column to keep track of original index before merge"""
        return "index_" + self.type

    @property
    @abstractmethod
    def on(self):
        """Final column on which to merge"""

    @property
    @abstractmethod
    def required_columns(self):
        """Columns that are required for the merge"""

    @property
    def created_columns(self):
        """Columns that are created only for the merge"""
        return [self.index_column]

    @property
    @abstractmethod
    def descriptive_columns(self):
        """Columns that are used to describe a row when reporting"""
        return [self.column]

    def transform(self, df):
        # Reset any (possibly multi-indexed) index, use integer indexing. This
        # makes sure that we have a column named `self.index_column`.
        df = df.reset_index(drop=True)
        df = df.reset_index(names=self.index_column)

        return df


class SimpleMerger(Merger):
    """Merger along a simple column"""

    def __init__(self, column, type=None):
        super().__init__(type=type)
        self.column = column

    @property
    def on(self):
        return self.column

    @property
    def required_columns(self):
        return [self.column, self.index_column]

    @property
    def descriptive_columns(self):
        return [self.column]


class ColumnsMerger(Merger):
    """Merger along a column created from several other ones"""

    def __init__(self, *columns, type=None, func=None):
        super().__init__(type=type)
        self.columns = columns
        self.slug_column = "guv_" + "_".join(columns)
        self.func = func

    @property
    def on(self):
        return self.slug_column

    @property
    def required_columns(self):
        return [self.slug_column , self.index_column]

    @property
    def created_columns(self):
        return [self.slug_column, self.index_column]

    @property
    def descriptive_columns(self):
        return self.columns

    def transform(self, df):
        df = super().transform(df)
        df = df.assign(**{self.slug_column: self.func(df)})

        return df


def _apply_processing(df, processing_type, processing):
    """Apply a processing a dataframe"""

    if processing is not None:
        if not isinstance(processing, (list, tuple)):
            processing = [processing]

        for op in processing:
            if isinstance(op, Operation):
                df = op.apply(df)
                logger.info(f"{processing_type} : %s", op.message())
            elif callable(op):
                if hasattr(op, "__desc__"):
                    logger.info(f"{processing_type} : %s", op.__desc__)
                else:
                    logger.info(processing_type)
                df = op(df)
            else:
                raise Exception(f"Unsupported {processing_type} operation", op)
    return df


class Aggregator:
    def __init__(
        self,
        left_df,
        right_df,
        left_on,
        right_on,
        preprocessing=None,
        postprocessing=None,
        subset=None,
        drop=None,
        rename=None,
        right_suffix="_y",
    ):
        self.left_merger = Merger.from_obj(left_on, type="left")
        self.right_merger = Merger.from_obj(right_on, type="right")
        self.left_df = left_df
        self._left_df = None
        self.right_df = right_df
        self._right_df = None
        self.right_suffix = right_suffix
        self.preprocessing = preprocessing
        self.postprocessing = postprocessing
        self.subset = subset
        self.drop = drop
        self.rename = rename

    @property
    def outer_merged_df(self):
        return self._outer_merged_df

    def _apply_transformations(self):
        # Select subset of columns. Add needed columns for the merge.
        if self.subset is not None:
            subset = [self.subset] if isinstance(self.subset, str) else self.subset
            check_if_present(self._right_df, subset)
            subset = list(set(self.right_merger.required_columns + subset))
            self._right_df = self._right_df[subset]

        # Drop columns. Dropping required columns for the merge is not allowed.
        if self.drop is not None:
            drop = [self.drop] if isinstance(self.drop, str) else self.drop

            inter = list(set(drop).intersection(set(self.right_merger.required_columns)))
            if inter:
                msg = ", ".join(f"`{c}`" for c in inter)
                raise Exception(f"Les colonnes {msg} sont nécessaires et ne peuvent pas être supprimées")

            self._right_df = self._right_df.drop(drop, axis=1, errors="ignore")

        if self.rename is not None:
            check_if_present(self._right_df, self.rename.keys())
            if (inter := set(self.rename.keys()).intersection(self.right_merger.required_columns)):
                inter_msg = ", ".join(f"`{c}`" for c in inter)
                raise Exception(f"Les clés {inter_msg} sont requises et ne peuvent pas être renommées")

            self._right_df = self._right_df.rename(columns=self.rename)

    def report_merge(self):
        df = self._outer_merged_df

        # Select right only and report
        df_ro = df.loc[df["_merge"] == "right_only"]

        # Get records in original right_df that have not been merged
        index_column = self.right_merger.index_column

        errors = self.right_df.loc[df_ro[index_column], self.right_merger.descriptive_columns]

        n = len(errors.index)
        if n > 0:
            logger.warning(
                "%s enregistrement%s n'%s pas pu être incorporé%s au fichier central",
                n,
                ps(n),
                plural(n, "ont", "a"),
                ps(n),
            )
            with pd.option_context("display.max_rows", 10,
                                   "display.max_columns", None,
                                   "display.width", 1000,
                                   "display.precision", 3,
                                   "display.colheader_justify", "left"):
                print(errors)

    def outer_aggregate(self):
        self._outer_aggregate()

        clean_df = self.clean_merge(self._outer_merged_df)
        return _apply_processing(clean_df, "Postprocessing", self.postprocessing)

    def _outer_aggregate(self):
        # Copy left and right dataframe before applying transformations
        self._left_df = self.left_df.copy()
        self._right_df = self.right_df.copy()

        # Apply preprocessing on _right_df
        self._right_df = _apply_processing(self._right_df, "Preprocessing", self.preprocessing)

        # Add required columns to be able to merge and display warnings
        self._right_df = self.right_merger.transform(self._right_df)
        self._left_df = self.left_merger.transform(self._left_df)

        # Rename, drop, select columns on _right_df
        self._apply_transformations()

        # Outer merge
        self._outer_merged_df = self._left_df.merge(
            self._right_df,
            left_on=self.left_merger.on,
            right_on=self.right_merger.on,
            how="outer",
            suffixes=("", self.right_suffix),
            indicator=True,
        )

    def clean_merge(self, df):
        # Drop added columns
        drop_cols = ["_merge"]
        drop_cols.extend(self.left_merger.created_columns)

        # Common created columns
        inter = list(set(self.left_merger.created_columns).intersection(set(self.right_merger.created_columns)))

        # Column that will receive a "_y" during merge
        if self.left_merger.on in inter and self.right_merger.on == self.left_merger.on:
            dups = [e + "_y" for e in inter if e != self.left_merger.on]
        else:
            dups = [e + "_y" for e in inter]

        drop_cols.extend(inter + dups)

        right_only = list(set(self.right_merger.created_columns) - set(self.left_merger.created_columns))
        drop_cols.extend(right_only)

        # Drop right primary key
        if self.right_merger.on != self.left_merger.on and self.left_merger.on not in drop_cols:
            drop_cols.append(self.right_merger.on)

        return df.drop(drop_cols, axis=1)

    def left_aggregate(self, report=True):
        """Return the aggregation."""

        # First an outer aggregation to be able to report
        self._outer_aggregate()

        if report:
            self.report_merge()

        # Left aggregation
        df = self.outer_merged_df
        self._left_merge_df = df.loc[df["_merge"].isin(['left_only', 'both'])]

        clean_df = self.clean_merge(self._left_merge_df)
        return _apply_processing(clean_df, "Postprocessing", self.postprocessing)


def make_column_merger(policy):
    def func(df, column):
        assert column in df.columns
        assert column + "_y" in df.columns

        column_y = column + '_y'
        column_not_na = df[column].notna()
        column_y_not_na = df[column_y].notna()
        mask_V_NA = column_not_na & ~column_y_not_na
        mask_NA_V = ~column_not_na & column_y_not_na
        mask_V_V = column_not_na & column_y_not_na & (df[column] != df[column_y])

        policy_mask = {
            ("NA", "V"): mask_NA_V,
            ("V", "NA"): mask_V_NA,
            ("V", "V"): mask_V_V
        }

        for k, v in policy.items():
            if v == "error":
                if any(mask_V_V):
                    raise Exception("Fusion impossible")
            elif v == "replace":
                mask = policy_mask[k]
                df.loc[mask, column] = df.loc[mask, column_y]
            elif v == "noop":
                pass
            else:
                raise ValueError

        df = df.drop(column_y, axis=1)
        return df

    return func


merge = make_column_merger({
    ("V", "V"): "error",
    ("NA", "V"): "replace",
    ("V", "NA"): "noop"
})

fill_na = make_column_merger({
    ("V", "V"): "noop",
    ("V", "NA"): "noop",
    ("NA", "V"): "replace",
})

replace = make_column_merger({
    ("V", "V"): "replace",
    ("V", "NA"): "noop",
    ("NA", "V"): "replace",
})

keep = make_column_merger({})

erase = make_column_merger({
    ("V", "V"): "replace",
    ("V", "NA"): "replace",
    ("NA", "V"): "replace",
})


def merge_columns(df, policy="merge"):
    duplicated_columns = [c for c in df.columns if c + "_y" in df.columns]
    func = {
        "merge": merge,
        "erase": erase,
        "keep": keep,
        "replace": replace,
        "fill_na": fill_na
    }.get(policy)

    for c in duplicated_columns:
        logger.warning("Tentative de fusion des colonnes `%s` et `%s`", c, c + "_y")
        try:
            df = func(df, c)
        except ImpossibleMerge:
            logger.warning("Fusion impossible, on garde les colonnes `%s` et `%s`", c, c + "_y")

    return df
