from collections.abc import Callable
from typing import Any

from .operation import Operation


class Documents:
    def fillna_column(
        self,
        colname: str,
        *,
        na_value: str | None = None,
        group_column: str | None = None
    ) -> None:
        ...

    def replace_regex(
        self,
        colname: str,
        *reps: str,
        new_colname: str | None = None,
        backup: bool | None = False,
        msg: str | None = None,
    ) -> None:
        ...

    def replace_column(
        self,
        colname: str,
        rep_dict: dict,
        new_colname: str | None = None,
        backup: bool | None = False,
        msg: str | None = None,
    ) -> None:
        ...

    def apply_df(self, func: Callable, msg: str | None = None) -> None:
        ...

    def apply_column(self, colname: str, func: Callable, msg: str | None = None) -> None:
        ...

    def compute_new_column(self, *cols: str, func: Callable, colname: str, msg: str | None = None) -> None:
        ...

    def add(self, filename: str, func: callable) -> None:
        ...

    def aggregate_self(self, *columns: str) -> None:
        ...

    def aggregate(
        self,
        filename: str,
        *,
        left_on: str | Callable[..., Any] | None = None,
        right_on: str | Callable[..., Any] | None = None,
        on: str | None = None,
        subset: str | list[str] | None = None,
        drop: str | list[str] | None = None,
        rename: dict[str, str] | None = None,
        preprocessing: Callable[..., Any] | Operation | None = None,
        postprocessing: Callable[..., Any] | Operation | None = None,
        read_method: Callable[..., Any] | None = None,
        kw_read: dict[str, Any] | None = None,
    ) -> None: ...

    def aggregate_moodle_grades(self, filename: str, rename: dict | None = None,) -> None:
        ...

    def aggregate_moodle_groups(self, filename: str, colname: str, backup: bool | None = False,) -> None:
        ...

    def aggregate_jury(self, filename: str) -> None:
        ...

    def aggregate_org(
        self,
        filename: str,
        colname: str,
        on: str | None = None,
        postprocessing: Callable | Operation | None = None,
    ) -> None:
        ...

    def flag(self, filename_or_string: str, *, colname: str, flags: list[str] | None = ["Oui", ""]) -> None:
        ...

    def apply_cell(self, name_or_email: str, colname: str, value, msg: str | None = None) -> None:
        ...

    def switch(
        self,
        filename_or_string: str,
        *,
        colname: str,
        backup: bool = False,
        new_colname: str | None = None,
    ) -> None:
        ...

    def add_moodle_listing(self, filename: str) -> None:
        ...

