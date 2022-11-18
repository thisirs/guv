class Documents:
    def fillna_column(
        self,
        colname: str,
        *,
        na_value: Optional[str] = None,
        group_column: Optional[str] = None
    ):
        pass

    def replace_regex(
        self,
        colname: str,
        *reps,
        new_colname: Optional[str] = None,
        backup: Optional[bool] = False,
        msg: Optional[str] = None,
    ):
        pass

    def replace_column(
        self,
        colname: str,
        rep_dict: dict,
        new_colname: Optional[str] = None,
        backup: Optional[bool] = False,
        msg: Optional[str] = None,
    ):
        pass

    def apply_df(self, func: Callable, msg: Optional[str] = None):
        pass

    def apply_column(self, colname: str, func: Callable, msg: Optional[str] = None):
        pass

    def compute_new_column(self, *cols: str, func: Callable, colname: str, msg: Optional[str] = None):
        pass

    def apply_cell(self, name_or_email: str, colname: str, value, msg: Optional[str] = None):
        pass

    def add(self, filename: str, func: callable):
        pass

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
        pass

    def aggregate_org(
        self,
        filename: str,
        colname: str,
        on: Optional[str] = None,
        postprocessing: Union[None, Callable, Operation] = None,
    ):
        pass

    def flag(self, filename_or_string: str, *, colname: str, flags: Optional[List[str]] = ["Oui", ""]):
        pass

    def switch(
        self,
        filename_or_string: str,
        *,
        colname: str,
        backup: bool = False,
        new_colname: Optional[str] = None,
    ):
        pass

    def aggregate_moodle_grades(self, filename: str, rename: Optional[dict] = None):
        pass

    def aggregate_jury(self, filename: str):
        pass
