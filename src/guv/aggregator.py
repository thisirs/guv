from abc import ABC, abstractmethod

import pandas as pd

from .exceptions import GuvUserError, ImpossibleMerge
from .logger import logger
from .operation import Operation
from .translations import _, ngettext
from .utils import check_if_present
from .utils_config import ask_choice


class Merger(ABC):
    def __init__(self, type=None, index=True):
        self.type = type
        self.index = index

    @staticmethod
    def from_obj(obj, type=None, index=True):
        if isinstance(obj, str):
            return SimpleMerger(obj, type=type, index=index)
        elif isinstance(obj, Merger):
            obj.type = type
            obj.index = True
            return obj
        elif isinstance(obj, list):
            mergers = [Merger.from_obj(e) for e in obj]
            return RecursiveMerger(*mergers, type=type, index=index)
        else:
            raise TypeError("Unknown merger", obj)

    @property
    @abstractmethod
    def on(self):
        """Final column on which to merge"""

    @property
    @abstractmethod
    def descriptive_columns(self):
        """Columns that are used to describe a row when reporting"""

    @property
    def required_columns(self):
        """Columns that are required for the merge"""
        if self.index:
            return ["index_" + self.type]
        return None

    @property
    def index_column(self):
        """Column to keep track of original index before merge"""
        if self.index:
            return "index_" + self.type
        return None

    @property
    def created_columns(self):
        """Columns that are created only for the merge"""
        if self.index:
            return [self.index_column]
        return []

    def transform(self, df):
        # Reset any (possibly multi-indexed) index, use integer indexing. This
        # makes sure that we have a column named `self.index_column`.
        if self.index:
            df = df.reset_index(drop=True)
            df = df.reset_index(names=self.index_column)

        return df


class SimpleMerger(Merger):
    """Merger along a simple column"""

    def __init__(self, *columns, type=None, index=True):
        super().__init__(type=type, index=index)
        self.columns = columns

    def fingerprint(self):
        return " ".join(self.columns)

    @property
    def on(self):
        return list(self.columns)

    @property
    def required_columns(self):
        return super().required_columns + list(self.columns)

    @property
    def descriptive_columns(self):
        return self.columns


class RecursiveMerger(Merger):
    def __init__(self, *mergers, type=None, index=True):
        super().__init__(type=type, index=index)
        self.mergers = mergers
        for merger in self.mergers:
            merger.index=False

    def fingerprint(self):
        return " ".join(item.fingerprint() for item in self.mergers)

    @property
    def required_columns(self):
        return super().required_columns + [e for merger in self.mergers for e in merger.required_columns]

    @property
    def created_columns(self):
        return super().created_columns + [e for merger in self.mergers for e in merger.created_columns]

    @property
    def descriptive_columns(self):
        return [e for merger in self.mergers for e in merger.descriptive_columns]

    @property
    def on(self):
        return [e for merger in self.mergers for e in merger.on]

    def transform(self, df):
        df = super().transform(df)

        for merger in self.mergers:
            df = merger.transform(df)

        return df


class ColumnsMerger(Merger):
    """Merger along a column created from several other ones"""

    def __init__(self, *columns, type=None, func=None, index=True):
        super().__init__(type=type, index=index)
        self.columns = columns
        self.slug_column = "guv_" + "_".join(columns)
        self.func = func

    def fingerprint(self):
        return self.columns

    @property
    def on(self):
        return [self.slug_column]

    @property
    def required_columns(self):
        return super().required_columns + [self.slug_column]

    @property
    def created_columns(self):
        return super().created_columns + [self.slug_column]

    @property
    def descriptive_columns(self):
        return list(self.columns)

    def transform(self, df):
        df = super().transform(df)
        df = df.assign(**{self.slug_column: self.func(df, *self.columns)})

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
                try:
                    df = op(df)
                except Exception as e:
                    msg = _("Error in `{m}`:".format(m=processing_type.lower()))
                    raise Exception(msg, repr(e)) from e
            else:
                raise TypeError(f"Unsupported {processing_type} operation", op)
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
        how="outer",
        merge_policy="merge",
        suffixes=("", "_y")
    ):
        self.left_merger = Merger.from_obj(left_on, type="left")
        self.right_merger = Merger.from_obj(right_on, type="right")
        self.left_df = left_df
        self._left_df = None
        self.right_df = right_df
        self._right_df = None
        self.suffixes = suffixes
        self.preprocessing = preprocessing
        self.postprocessing = postprocessing
        self.subset = subset
        self.drop = drop
        self.rename = rename
        self.how = how
        self.merge_policy = merge_policy
        self._df_outer = None

    def merge(self):
        check_if_present(self.left_df, self.left_merger.descriptive_columns)
        check_if_present(self.right_df, self.right_merger.descriptive_columns)

        df_outer = self._df_outer = self._outer_merge()

        return self._cleanup_after_merge(df_outer)

    def _cleanup_after_merge(self, df_outer):
        if self.how == "outer_raw":
            return merge_columns(df_outer, policy=self.merge_policy)

        elif self.how == "outer":
            columns = _drop_cols(df_outer.columns, self.left_merger, self.right_merger)
            df_clean = df_outer.drop(columns, axis=1)
            df_merge = merge_columns(df_clean, policy=self.merge_policy)
            return _apply_processing(df_merge, "Postprocessing", self.postprocessing)

        elif self.how == "left":
            df_left = df_outer.loc[df_outer["_merge"].isin(['left_only', 'both'])]

            columns = _drop_cols(df_outer.columns, self.left_merger, self.right_merger)
            df_clean = df_left.drop(columns, axis=1)

            df_merge = merge_columns(df_clean, policy=self.merge_policy)
            df_postproc = _apply_processing(df_merge, "Postprocessing", self.postprocessing)
            return df_postproc

        else:
            raise ValueError("Unknown `how` method: %s" % self.how)

    def _outer_merge(self):
        # Copy left and right dataframe before applying transformations
        self._left_df = self.left_df.copy()
        self._right_df = self.right_df.copy()

        # Apply preprocessing on _right_df
        self._right_df = _apply_processing(self._right_df, "Preprocessing", self.preprocessing)

        # Add required columns to be able to merge and display warnings
        self._right_df = self.right_merger.transform(self._right_df)
        self._left_df = self.left_merger.transform(self._left_df)

        dup_right = self._right_df.duplicated(subset=self.right_merger.on)
        if dup_right.any():
            errors = self._right_df.loc[dup_right, self.right_merger.descriptive_columns]

            n = len(errors.index)
            logger.error(
                ngettext(
                    "The following record is not unique",
                    "The following records are not unique",
                    n
                )
            )
            print(errors.to_string(index=False))
            raise GuvUserError

        # Rename, drop, select columns on _right_df
        self._apply_transformations()

        # Outer merge
        outer_merge = self._left_df.merge(
            self._right_df,
            left_on=self.left_merger.on,
            right_on=self.right_merger.on,
            how="outer",
            suffixes=self.suffixes,
            indicator=True,
        )

        return outer_merge

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
                raise GuvUserError(_("The columns {msg} are required and cannot be removed").format(msg=msg))

            self._right_df = self._right_df.drop(drop, axis=1, errors="ignore")

        if self.rename is not None:
            check_if_present(self._right_df, self.rename.keys())
            if (inter := set(self.rename.keys()).intersection(self.right_merger.required_columns)):
                inter_msg = ", ".join(f"`{c}`" for c in inter)
                raise GuvUserError(_("The keys {inter_msg} are required and cannot be renamed").format(inter_msg=inter_msg))

            self._right_df = self._right_df.rename(columns=self.rename)

    def manual_merge(self):
        if self.how != "outer":
            raise ValueError("Manual merge for outer merge only")

        check_if_present(self.left_df, self.left_merger.descriptive_columns)
        check_if_present(self.right_df, self.right_merger.descriptive_columns)

        self._df_outer = self._outer_merge()
        df_both = self._df_outer.loc[self._df_outer["_merge"] == "both"]

        lo = self._df_outer.loc[self._df_outer["_merge"] == "left_only"]
        lo_index_column = self.left_merger.index_column
        origin_lo = self._left_df.loc[lo[lo_index_column]]

        for row in origin_lo.itertuples(index=True):
            description = ", ".join(str(getattr(row, e)) for e in self.left_merger.descriptive_columns)
            logger.warning(_("The record `{desc}` is missing from the data to be aggregated").format(desc=description))

        ro = self._df_outer.loc[self._df_outer["_merge"] == "right_only"]
        ro_index_column = self.right_merger.index_column
        origin_ro = self._right_df.loc[ro[ro_index_column]]

        for row in origin_ro.itertuples(index=True):
            description = ", ".join(str(getattr(row, e)) for e in self.right_merger.descriptive_columns)
            logger.warning(_("The record `{desc}` is missing from base data").format(desc=description))

        for row in lo.itertuples(index=True):
            if len(ro.index != 0):
                origin_lo_row = origin_lo.loc[getattr(row, lo_index_column)]
                description = ", ".join(origin_lo_row[e] for e in self.left_merger.descriptive_columns)
                logger.info(_("Searching for match for `%s` :"), description)

                for i, row_ro in enumerate(ro.itertuples(index=True)):
                    origin_ro_row = origin_ro.loc[getattr(row_ro, ro_index_column)]
                    description = ", ".join(origin_ro_row[e] for e in self.right_merger.descriptive_columns)
                    print(f"  ({i}) {description}")

                choice = ask_choice(
                    _("Choice? (enter if no match) "),
                    {**{str(i): i for i in range(len(origin_ro.index))}, "": None}
                )

                if choice is not None:
                    row_merge = lo.loc[row.Index, :].combine_first(ro.iloc[choice, :])
                    ro = ro.drop(index=ro.iloc[[choice]].index)
                else:
                    row_merge = lo.loc[row.Index, :].copy()
            else:
                row_merge = lo.loc[row.Index, :].copy()

            row_merge["_merge"] = "both"
            df_both = pd.concat((df_both, row_merge.to_frame().T))

        return self._cleanup_after_merge(df_both)

    def report(self):
        if self._df_outer is None:
            raise RuntimeError("Call .merge() first before reporting")

        df = self._df_outer
        if self.how == "outer_raw":
            pass

        elif self.how == "outer":
            pass

        elif self.how == "left":
            # Select right only and report
            df_ro = df.loc[df["_merge"] == "right_only"]

            # Get records in original right_df that have not been merged
            index_column = self.right_merger.index_column

            errors = self.right_df.loc[df_ro[index_column], self.right_merger.descriptive_columns]

            n = len(errors.index)
            if n > 0:
                logger.warning(
                    ngettext(
                        "{n} record could not be incorporated into the central file",
                        "{n} records could not be incorporated into the central file",
                        n
                    ).format(n=n)
                )
                print(errors.to_string(index=False))


def _drop_cols(columns, left_merger, right_merger):
    blah = {
        (True, True, True, True): lambda x: [x],
        (True, True, True, False): lambda x: [x, x + "_y"],
        (True, True, False, True): lambda x: [x],
        (True, True, False, False): lambda x: [x, x + "_y"],
        (True, False, True, True): lambda x: [],
        (True, False, True, False): lambda x: [x],
        (True, False, False, True): lambda x: [x],
        (True, False, False, False): lambda x: [x],
        (False, True, True, True): lambda x: [x + "_y"],
        (False, True, True, False): lambda x: [x + "_y"],
        (False, True, False, True): lambda x: [x],
        (False, True, False, False): lambda x: [x],
        (False, False, True, True): lambda x: [],
        (False, False, True, False): lambda x: [],
        (False, False, False, True): lambda x: [] if x + "_y" in columns else [x],
        (False, False, False, False): lambda x: [],
    }

    drop_cols = ["_merge"]
    for colname in columns:
        is_created_left = colname in left_merger.created_columns
        is_created_right = colname in right_merger.created_columns
        is_on_left = colname in left_merger.on
        is_on_right = colname in right_merger.on
        func = blah[(is_created_left, is_created_right, is_on_left, is_on_right)]
        drop_cols.extend(func(colname))
    return drop_cols


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
                    raise ImpossibleMerge(_("Merge impossible"))
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
        if policy == "merge":
            logger.warning(_("Attempting to merge columns `{col1}` and `{col2}`").format(col1=c, col2=c + "_y"))
        try:
            df = func(df, c)
        except ImpossibleMerge:
            logger.warning(_("Merge impossible, keeping columns `{col1}` and `{col2}`").format(col1=c, col2=c + "_y"))

    return df
