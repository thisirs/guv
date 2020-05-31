import numpy as np
import string
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
