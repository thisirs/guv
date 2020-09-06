import os
import sys
import re
import string
import argparse
import hashlib
import pandas as pd
import numpy as np
from types import SimpleNamespace, GeneratorType
from functools import wraps
from datetime import timedelta
import unidecode
import textwrap

from doit.action import PythonAction
from doit.exceptions import TaskFailed


def rel_to_dir(path, root):
    common_prefix = os.path.commonprefix([path, root])
    return os.path.relpath(path, common_prefix)


def check_columns(dataframe, columns, **kwargs):
    if isinstance(columns, str):
        columns = [columns]
    missing_cols = [c for c in columns if c not in dataframe.columns]

    if missing_cols:
        s = "s" if len(missing_cols) > 1 else ""
        missing_cols = ", ".join(f"`{e}'" for e in missing_cols)
        avail_cols = ", ".join(f"`{e}'" for e in dataframe.columns)
        if 'file' in kwargs and 'base_dir' in kwargs:
            fn = rel_to_dir(kwargs['file'], kwargs["base_dir"])
            msg = f"Colonne{s} manquante{s}: {missing_cols} dans le dataframe issu du fichier {fn}. Colonnes disponibles: {avail_cols}"
        else:
            msg = f"Colonne{s} manquante{s}: {missing_cols}. Colonnes disponibles: {avail_cols}"
        raise Exception(msg)


def fillna_column(colname, na_value="ABS"):
    """Utilisable dans postprocessing ou preprocessing où à la place de
    aggregate dans le AGGREGATE_DOCUMENTS."""

    def func(df, path=None):
        check_columns(df, [colname])
        df[colname].fillna("ABS", inplace=True)
        return df
    return func


def replace_regex(colname, *reps, new_colname=None):
    """Utilisable dans postprocessing ou preprocessing ou à la place de
    aggregate dans le AGGREGATE_DOCUMENTS."""

    def func(df, path=None):
        check_columns(df, colname)
        s = df[colname]
        for rep in reps:
            s.replace(*rep, regex=True, inplace=True)
        cn = new_colname if new_colname is not None else colname
        df = df.assign(**{cn: s})
        return df
    return func


def replace_column(colname, rep_dict, new_colname=None):
    """Utilisable dans postprocessing ou preprocessing où à la place de
    aggregate dans le AGGREGATE_DOCUMENTS."""

    def func(df, path=None):
        check_columns(df, colname)
        col_ref = df[colname].replace(rep_dict)
        cn = new_colname if new_colname is not None else colname
        df = df.assign(**{cn: col_ref})
        return df
    return func


def aggregate(left_on, right_on, preprocessing=None, postprocessing=None, subset=None, drop=None, rename=None, read_method=None, kw_read={}):
    def aggregate0(left_df, path):
        nonlocal left_on, right_on, subset, drop

        # Columns that will be removed after merging
        drop_cols = []
        left_on_is_added = False

        # Add column if callable, check if it exists
        if callable(left_on):
            left_on = left_on(left_df)
            left_df = left_df.assign(**{left_on.name: left_on.values})
            left_on = left_on.name
            left_on_is_added = True

        if isinstance(left_on, str):
            # Check that left_on column exists
            check_columns(left_df, left_on)
        else:
            raise Exception("Unsupported type for left_on")

        # Infer a read method if not provided
        if read_method is None:
            if path.endswith('.csv'):
                right_df = pd.read_csv(path, **kw_read)
            elif path.endswith('.xlsx') or path.endswith('.xls'):
                right_df = pd.read_excel(path, **kw_read)
            else:
                raise Exception('No read method and unsupported file extension')
        else:
            right_df = read_method(path, **kw_read)

        if preprocessing is not None:
            right_df = preprocessing(right_df)

        # Add column if callable, check if it exists
        if callable(right_on):
            right_on = right_on(right_df)
            right_df = right_df.assign(**{right_on.name: right_on.values})
            right_on = right_on.name

        if isinstance(right_on, str):
            # Check that right_on column exists
            check_columns(right_df, right_on)
        else:
            raise Exception("Unsupported type for right_on")

        # Extract subset of columns, right_on included
        if subset is not None:
            if isinstance(subset, str):
                subset = [subset]
            right_df = right_df[list(set([right_on] + subset))]

        # Allow to drop columns, right_on not allowed
        if drop is not None:
            if isinstance(drop, str):
                drop = [drop]
            if right_on in drop:
                raise Exception('On enlève pas la clé')
            right_df = right_df.drop(drop, axis=1, errors='ignore')

        # Rename columns in data to be merged
        if rename is not None:
            if right_on in rename:
                raise Exception('Pas de renommage de la clé possible')
            right_df = right_df.rename(columns=rename)

        # Columns to drop after merge
        drop_cols = ['_merge']
        if right_on in left_df.columns:
            drop_cols += [right_on + "_y"]
        else:
            drop_cols += [right_on]

        if left_on_is_added:
            drop_cols += [left_on]

        # Record duplicated columns to be eventually merged later
        duplicated_columns = set(left_df.columns).intersection(set(right_df.columns))
        duplicated_columns = duplicated_columns.difference(set([left_on, right_on]))

        # Outer merge
        merged_df = left_df.merge(right_df,
                                  left_on=left_on,
                                  right_on=right_on,
                                  how='outer',
                                  suffixes=('', '_y'),
                                  indicator=True)

        # Select like how='left' as result
        agg_df = merged_df[merged_df["_merge"].isin(['left_only', 'both'])]

        # Select right only and report
        merged_df_ro = merged_df[merged_df["_merge"] == 'right_only']
        if right_on in left_df.columns:
            key = right_on + "_y"
        else:
            key = right_on

        for index, row in merged_df_ro.iterrows():
            print("WARNING: identifiant présent dans le document à aggréger mais introuvable dans la base de données :", row[key])

        if postprocessing is not None:
            print("Postprocessing")
            agg_df = postprocessing(agg_df)

        # Try to merge columns
        for c in duplicated_columns:
            c_y = c + '_y'
            print('Trying to merge columns %s and %s...' % (c, c_y), end='')
            if any(agg_df[c_y].notna() & agg_df[c].notna()):
                print('failed')
                continue
            else:
                agg_df.loc[:, c] = agg_df.loc[:, c].fillna(agg_df.loc[:, c_y])
                drop_cols.append(c_y)
                print('done')

        # Drop useless columns
        agg_df = agg_df.drop(drop_cols, axis=1, errors='ignore')

        return agg_df

    return aggregate0


def actionfailed_on_exception(func):
    """Decorator to allow a task function to raise an exception."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            ret = func(*args, **kwargs)
            if isinstance(ret, GeneratorType):
                ret = (t for t in list(ret))
            return ret
        except ParseArgsFailed as e:  # Cli parser failed
            kwargs = {
                'actions': [ParseArgAction(e.parser, e.args)],
            }
            return kwargs
        except Exception as e:
            tf = TaskFailed(e.args)
            kwargs = {
                'actions': [lambda: tf],
            }
            return kwargs
    return wrapper


def taskfailed_on_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return TaskFailed(e.args)
    return wrapper


def parse_args(task, *args, **kwargs):
    # Command-line arguments
    argv = kwargs.get("argv", sys.argv)
    if len(argv) < 2:          # doit_utc a_task [args]
        raise Exception("Wrong number of arguments in sys.argv")

    # Argument parser for task
    task_name = task.__name__.split("_", maxsplit=1)[1]
    parser = argparse.ArgumentParser(
        description=task.__doc__,
        prog=f"doit-utc {task_name}"
    )
    for arg in args:
        parser.add_argument(*arg.args, **arg.kwargs)

    if len(argv) == 2 and argv[1] == "parsearg":
        raise ParseArgsFailed(parser)

    # Base task specified in command line
    base_task = argv[1]

    if task_name == base_task:  # Args are relevant
        sargv = argv[2:]
        return parser.parse_args(sargv)
    else:
        # Test if dependant task needs arguments; current ones are not
        # relevant

        # If parse_args fails, don't show error message and don't sys.exit()
        def dummy(msg):
            raise ParseArgsFailed(parser)
        parser.error = dummy

        return parser.parse_args(args=[])


def argument(*args, **kwargs):
    return SimpleNamespace(args=args, kwargs=kwargs)


def add_templates(**templates):
    def decorator(func):
        for key, value in templates.items():
            setattr(func, key, value)
        return func
    return decorator


def hexxor(a, b):  # xor two hex strings of the same length
    return "".join(["%x" % (int(x, 16) ^ int(y, 16)) for (x, y) in zip(a, b)])


def md5(fname):
    hash_md5 = hashlib.md5()
    hash_md5.update(fname.encode('utf8'))
    return hash_md5.hexdigest()


def hash_rot_md5(a):
    "Return a hash invariant by rotation"
    def substring():
        b = a + a
        for i in range(len(a)):
            yield b[i : (i + len(a))]

    s0 = "0" * len(a)
    s0 = md5(s0)
    for s in substring():
        s0 = hexxor(s0, md5(s))

    return s0


def slugrot_string(e):
    "Rotation-invariant hash on a string"

    e0 = unidecode.unidecode(e).lower()
    e0 = ''.join(e0.split())
    return hash_rot_md5(e0)


def slugrot(*columns):
    "Rotation-invariant hash function on a dataframe"

    def func(df):
        check_columns(df, columns)
        s = df[list(columns)].apply(
            lambda x: "".join(x.astype(str)),
            axis=1
        )

        s = s.apply(slugrot_string)
        s.name = "_".join(columns)
        return s

    return func


def aggregate_org(colname):
    def aggregate_org0(left_df, path):
        if not path.endswith('.org'):
            raise Exception(f"{path} n'est pas un fichier org")

        left_df[colname] = ""

        # Add column that acts as a primary key
        tf_df = slugrot("Nom", "Prénom")
        left_df["fullname_slug"] = tf_df(left_df)

        infos = open(path, 'r').read()
        if infos:
            for chunk in re.split("^\\* *", infos, flags=re.MULTILINE):
                if not chunk:
                    continue
                etu, *text = chunk.split("\n", maxsplit=1)
                text = "\n".join(text).strip("\n")
                text = textwrap.dedent(text)
                slugname = slugrot_string(etu)

                res = left_df.loc[left_df.fullname_slug == slugname]
                if len(res) == 0:
                    raise Exception('Pas de correspondance pour `{:s}`'.format(etu))
                elif len(res) > 1:
                    raise Exception('Plusieurs correspondances pour `{:s}`'.format(etu))

                left_df.loc[res.index[0], colname] = text

        df = left_df.drop('fullname_slug', axis=1)
        return df
    return aggregate_org0


def skip_range(d1, d2):
    return [d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)]


def skip_week(d1, weeks=1):
    return [d1 + timedelta(days=x) for x in range(7*weeks-1)]


LATEX_SUBS = (
    (re.compile(r'\\'), r'\\textbackslash'),
    (re.compile(r'([{}_#%&$])'), r'\\\1'),
    (re.compile(r'~'), r'\~{}'),
    (re.compile(r'\^'), r'\^{}'),
    (re.compile(r'"'), r"''"),
    (re.compile(r'\.\.\.+'), r'\\ldots'))


def escape_tex(value):
    newval = value
    for pattern, replacement in LATEX_SUBS:
        newval = pattern.sub(replacement, newval)
    return newval


def lib_list(lib):
    """Return a numeric tuple to sort course codenames"""
    m = re.match('([CDT])([0-9]*)([AB]*)', lib)
    crs = {'C': 0, 'D': 1, 'T': 2}[m.group(1)]
    no = int('0' + m.group(2))
    sem = 0 if m.group(3) == 'A' else 1
    return crs, no, sem


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

    frequency = make_groups0(n, proportions)
    return np.repeat(names, frequency)


def make_groups0(n, proportions):
    proportions = np.array(proportions)
    proportions = proportions / sum(proportions)

    frequency = np.floor(n * proportions).astype(int)
    order = np.argsort(frequency)
    rest = n - sum(frequency)
    frequency[order[:rest]] += 1

    return frequency


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
