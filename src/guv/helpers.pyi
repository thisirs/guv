class Documents:
    def fillna_column(
        self,
        colname: str,
        *,
        na_value: Optional[str] = None,
        group_column: Optional[str] = None
    ):
        ...

    def replace_regex(
        self,
        colname: str,
        *reps,
        new_colname: Optional[str] = None,
        backup: Optional[bool] = False,
        msg: Optional[str] = None,
    ):
        ...

    def replace_column(
        self,
        colname: str,
        rep_dict: dict,
        new_colname: Optional[str] = None,
        backup: Optional[bool] = False,
        msg: Optional[str] = None,
    ):
        ...

    def apply_df(self, func: Callable, msg: Optional[str] = None):
        ...

    def apply_column(self, colname: str, func: Callable, msg: Optional[str] = None):
        ...

    def compute_new_column(self, *cols: str, func: Callable, colname: str, msg: Optional[str] = None):
        ...

    def apply_cell(self, name_or_email: str, colname: str, value, msg: Optional[str] = None):
        ...

    def add(self, filename: str, func: callable):
        ...

    def aggregate(
        self,
        filename: str,
        *,
        left_on: Union[None, str, callable] = None,
        right_on: Union[None, str, callable] = None,
        on: Optional[str] = None,
        subset: Union[None, str, List[str]] = None,
        drop: Union[None, str, List[str]] = None,
        rename: Optional[dict] = None,
        preprocessing: Union[None, Callable, Operation] = None,
        postprocessing: Union[None, Callable, Operation] = None,
        read_method: Optional[Callable] = None,
        kw_read: Optional[dict] = {}
    ):
        ...

    def aggregate_org(
        self,
        filename: str,
        colname: str,
        on: Optional[str] = None,
        postprocessing: Union[None, Callable, Operation] = None,
    ):
        ...

    def flag(self, filename_or_string: str, *, colname: str, flags: Optional[List[str]] = ["Oui", ""]):
        ...

    def switch(
        self,
        filename_or_string: str,
        *,
        colname: str,
        backup: bool = False,
        new_colname: Optional[str] = None,
    ):
        ...

    def aggregate_moodle_groups(self, filename: str, colname: str):
        ...

    def aggregate_moodle_grades(self, filename: str, rename: Optional[dict] = None,):
        ...

    def aggregate_jury(self, filename: str):
        ...

