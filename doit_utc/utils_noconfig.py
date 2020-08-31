import string
import numpy as np
from doit.action import PythonAction
from doit.exceptions import TaskFailed


class FormatDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def pformat(s, **kwargs):
    formatter = string.Formatter()
    mapping = FormatDict(**kwargs)
    return formatter.vformat(s, (), mapping)


class ParseArgsFailed(Exception):
    def __init__(self, parser):
        super().__init__()
        self.parser = parser


class ParseArgAction(PythonAction):
    def __init__(self, parser, args):
        tf = TaskFailed(args)
        super().__init__(lambda: tf)
        self.parser = parser


def make_groups(n, proportions, name_gen):
    n_groups = len(proportions)
    names = [next(name_gen) for i in range(n_groups)]

    proportions = np.array(proportions)
    proportions = proportions / sum(proportions)

    frequency = np.floor(n * proportions).astype(int)
    order = np.argsort(frequency)
    rest = n - sum(frequency)
    frequency[order[:rest]] += 1

    return np.repeat(names, frequency)
def sort_values(df, columns):
    """Trier le DataFrame en prenant en compte les accents"""

    drop_cols = []
    sort_cols = []
    for colname in columns:
        try:
            s = df[colname].str.normalize("NFKD")
            new_colname = colname + "_NFKD"
            df = df.assign(**{new_colname: s})
            sort_cols.append(new_colname)
            drop_cols.append(new_colname)
        except AttributeError:
            sort_cols.append(colname)

    df = df.sort_values(sort_cols)
    df = df.drop(columns=drop_cols)
    return df
