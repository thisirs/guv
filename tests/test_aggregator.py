import numpy as np
import pandas as pd
from pandas import testing as tm
import pytest
from guv.aggregator import Aggregator, ColumnsMerger, merge_columns, merge, complete_left, complete_right, keep_left, keep_right
from guv.helpers import id_slug, concat


data = [
    (
        pd.DataFrame({"K": [1, 2, 3], "A": [1, 2, 3]}),
        pd.DataFrame({"K": [1, 2, 3, 4], "B": [1, 2, 3, 4]}),
        "K",
        "K",
        ["K", "A", "B"],
        4
    ),
    (
        pd.DataFrame({"K": [1, 2, 3], "A": [1, 2, 3]}),
        pd.DataFrame({"K": [1, 2, 3, 4], "A": [1, 2, 3, 4]}),
        "K",
        "K",
        ["K", "A", "A_y"],
        4
    ),
    (
        pd.DataFrame({"K1": [1, 2, 3], "A": [1, 2, 3]}),
        pd.DataFrame({"K2": [1, 2, 3, 4], "B": [1, 2, 3, 4]}),
        "K1",
        "K2",
        ["K1", "A", "B"],
        4
    ),
    (
        pd.DataFrame({"K1": [1, 2, 3], "A": [1, 2, 3]}),
        pd.DataFrame({"K2": [1, 2, 3, 4], "A": [1, 2, 3, 4]}),
        "K1",
        "K2",
        ["K1", "A", "A_y"],
        4
    ),
    (
        pd.DataFrame({"K1": ["A", "B", "C"], "K2": ["a", "b", "c"], "A": [1, 2, 3]}),
        pd.DataFrame({"K2": ["Aa", "Bb", "Cc", "Dd"], "B": [1, 2, 3, 4]}),
        concat("K1", "K2"),
        "K2",
        ["K1", "K2", "K2_y", "A", "B"],
        4
    ),
    (
        pd.DataFrame({"K1": ["A", "B", "C"], "K2": ["a", "b", "c"], "A": [1, 2, 3]}),
        pd.DataFrame({"K1": ["A", "B", "C"], "K2": ["a", "b", "c"], "A": [1, 2, 3]}),
        concat("K1", "K2"),
        concat("K1", "K2"),
        ["K1", "K2", "K1_y", "K2_y", "A", "A_y"],
        3
    ),
    (
        pd.DataFrame({"K1": ["Â", "B", "C"], "K2": ["à", "b", "ç"], "A": [1, 2, 3]}),
        pd.DataFrame({"K2": ["Aa", "Bb", "Cc", "Dd"], "B": [1, 2, 3, 4]}),
        id_slug("K1", "K2"),
        id_slug("K2"),
        ["K1", "K2", "K2_y", "A", "B"],
        4
    ),
    (
        pd.DataFrame({"K1": ["A", "b", "C"], "K2": ["â", "b", "c"], "A": [1, 2, 3]}),
        pd.DataFrame({"K1": ["à", "B", "C"], "K2": ["a", "b", "c"], "A": [1, 2, 3]}),
        id_slug("K1", "K2"),
        id_slug("K1", "K2"),
        ["K1", "K2", "K1_y", "K2_y", "A", "A_y"],
        3
    ),
]


@pytest.mark.parametrize("left_df, right_df, left_on, right_on, columns, num", data)
def test_outer(left_df, right_df, left_on, right_on, columns, num):
    agg = Aggregator(left_df=left_df, right_df=right_df, left_on=left_on, right_on=right_on)
    df = agg.outer_aggregate()
    assert set(df.columns) == set(columns)
    assert len(df.index) == num


data = [
    (
        pd.DataFrame({"K": [1, 2, 3], "A": [1, 2, 3]}),
        pd.DataFrame({"K": [1, 2, 3, 4], "B": [1, 2, 3, 4], "C": [1, 2, 3, 4]}),
        "K",
        "K",
        ["K", "A", "B"],
        4,
        dict(subset=["B"])
    ),
    (
        pd.DataFrame({"K": [1, 2, 3], "A": [1, 2, 3]}),
        pd.DataFrame({"K": [1, 2, 3, 4], "B": [1, 2, 3, 4], "C": [1, 2, 3, 4]}),
        "K",
        "K",
        ["K", "A", "C"],
        4,
        dict(drop=["B"])
    ),
    (
        pd.DataFrame({"K": [1, 2, 3], "A": [1, 2, 3]}),
        pd.DataFrame({"K": [1, 2, 3, 4], "B": [1, 2, 3, 4], "C": [1, 2, 3, 4]}),
        "K",
        "K",
        ["K", "A", "BB", "C"],
        4,
        dict(rename=dict(B="BB"))
    ),
]


@pytest.mark.parametrize("left_df, right_df, left_on, right_on, columns, num, kwargs", data)
def test_outer_transformation(left_df, right_df, left_on, right_on, columns, num, kwargs):
    agg = Aggregator(left_df=left_df, right_df=right_df, left_on=left_on, right_on=right_on, **kwargs)
    df = agg.outer_aggregate()
    assert set(df.columns) == set(columns)
    assert len(df.index) == num



n = np.nan
data = [
    (
        merge,
        [1],
        [2],
        "error"
    ),
    (
        merge,
        [1, n, 1, n],
        [n, n, 1, 1],
        [1, n, 1, 1]
    ),
    (
        complete_left,
        [1, n, 1, n],
        [n, n, 2, 2],
        [1, n, 1, 2]
    ),
    (
        complete_right,
        [1, n, 1, n],
        [n, n, 2, 2],
        [1, n, 2, 2]
    ),
    (
        keep_left,
        [1, n, 1, n],
        [n, n, 2, 2],
        [1, n, 1, n]
    ),
    (
        keep_right,
        [1, n, 1, n],
        [n, n, 2, 2],
        [n, n, 2, 2]
    ),

]
@pytest.mark.parametrize("merge_method, col1, col2, result", data)
def test_merge_column(merge_method, col1, col2, result):
    df = pd.DataFrame({"K": pd.Series(col1), "K_y": pd.Series(col2)})
    if result == "error":
        with pytest.raises(Exception):
            df = merge_method(df, "K")
    else:
        df = merge_method(df, "K")
        tm.assert_series_equal(df["K"], pd.Series(result), check_names=False)

