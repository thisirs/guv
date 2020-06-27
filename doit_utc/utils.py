import os
import sys
import re
import time
import argparse
import hashlib
from types import SimpleNamespace, GeneratorType
from functools import wraps
from datetime import timedelta
import pandas as pd
import unidecode
import textwrap

from doit.exceptions import TaskFailed

from .utils_noconfig import ParseArgsFailed, ParseArgAction

from .config import settings


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


def check_columns(dataframe, columns, **kwargs):
    if isinstance(columns, str):
        columns = [columns]
    missing_cols = [c for c in columns if c not in dataframe.columns]

    if missing_cols:
        s = "s" if len(missing_cols) > 1 else ""
        missing_cols = ", ".join(f"`{e}'" for e in missing_cols)
        avail_cols = ", ".join(f"`{e}'" for e in dataframe.columns)
        if 'file' in kwargs:
            fn = rel_to_dir(kwargs['file'], settings.BASE_DIR)
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


def selected_uv(all=False):
    if all:
        for planning, settings0 in settings.PLANNINGS.items():
            uvp = settings0['UVS']
            for uv in uvp:
                yield planning, uv, {'planning': planning, 'uv': uv}
    else:
        for planning, settings0 in settings.PLANNINGS.items():
            uvp = settings0['UVS']
            for uv in set(settings.SELECTED_UVS).intersection(set(uvp)):
                yield planning, uv, {'planning': planning, 'uv': uv}


def get_unique_uv():
    uvs = list(selected_uv())
    if len(uvs) != 1:
        uvs = [uv for _, uv, _ in uvs]
        raise Exception(f"Une seule UV doit être sélectionnée. Les UVs sélectionnées sont: {', '.join(uvs)}")
    return uvs[0]


def documents(fn, **info):
    if "local" in info:
        base_dir = os.path.basename(settings.BASE_DIR)
    else:
        base_dir = settings.BASE_DIR

    if 'uv' in info or 'ue' in info:
        uv = info.get('uv', info.get('ue'))
        return os.path.join(base_dir, uv, 'documents', fn)
    else:
        return os.path.join(base_dir, 'documents', fn)


def generated(fn, **info):
    if "local" in info:
        base_dir = ""
    else:
        base_dir = settings.BASE_DIR

    if 'uv' in info or 'ue' in info:
        uv = info.get('uv', info.get('ue'))
        return os.path.join(base_dir, uv, 'generated', fn)
    else:
        return os.path.join(base_dir, 'generated', fn)


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

        if postprocessing is not None:
            agg_df = postprocessing(agg_df)

        return agg_df

    return aggregate0


def skip_range(d1, d2):
    return [d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)]


def skip_week(d1, weeks=1):
    return [d1 + timedelta(days=x) for x in range(7*weeks-1)]


def rel_to_dir(path, root):
    common_prefix = os.path.commonprefix([path, root])
    return os.path.relpath(path, common_prefix)


class Output():
    def __init__(self, target, protected=False):
        self.target = target
        self.protected = protected

    def __enter__(self):
        if os.path.exists(self.target):
            if self.protected:
                while True:
                    try:
                        choice = input('Le fichier `%s'' existe déjà. Écraser (d), garder (g), sauvegarder (s), annuler (a) ? ' % rel_to_dir(self.target, settings.BASE_DIR))
                        if choice == 'd':
                            os.remove(self.target)
                        elif choice == 's':
                            parts = os.path.splitext(self.target)
                            timestr = time.strftime("_%Y%m%d-%H%M%S")
                            target0 = parts[0] + timestr + parts[1]
                            os.rename(self.target, target0)
                        elif choice == 'g':
                            return lambda: 1/0
                        elif choice == 'a':
                            raise Exception('Annulation')
                        else:
                            raise ValueError
                    except ValueError:
                        continue
                    else:
                        break
            else:
                print('Écrasement du fichier `%s\'' %
                      rel_to_dir(self.target, settings.BASE_DIR))
        else:
            dirname = os.path.dirname(self.target)
            if not os.path.exists(dirname):
                os.makedirs(dirname)

        return lambda: self.target

    def __exit__(self, type, value, traceback):
        if type is ZeroDivisionError:
            return True
        if type is None:
            print(f"Wrote `{rel_to_dir(self.target, settings.BASE_DIR)}'")


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


def create_plannings(planning_type):
    """Generate list of working days according to planning"""

    def generate_days(beg, end, skip, turn, course):
        """Generate working days from BEG to END"""

        daynames = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
        days = []
        delta = end - beg
        semaine = {'Lundi': 0, 'Mardi': 0, 'Mercredi': 0, 'Jeudi': 0, 'Vendredi': 0}

        nweek = 0

        for i in range(delta.days + 1):
            d = beg + timedelta(days=i)

            # Lundi
            if i % 7 == 0:
                nweek += 1

            # Ignore week-end
            if d.weekday() in [5, 6]:
                continue

            # Skip days
            if d in skip:
                continue

            # Get real day
            day = turn[d] if d in turn else daynames[d.weekday()]

            # Get week A or B
            if course == 'T':
                sem = 'A' if semaine[day] % 2 == 0 else 'B'
                numAB = semaine[day] // 2 + 1
                semaine[day] += 1
                num = semaine[day]
            elif course in ['C', 'D']:
                semaine[day] += 1
                numAB = None
                sem = None
                num = semaine[day]
            else:
                raise Exception("course inconnu")

            if d in turn:
                days.append((d, turn[d], sem, num, numAB, nweek))
            else:
                days.append((d, daynames[d.weekday()], sem, num, numAB, nweek))

        return days

    beg = settings.PLANNINGS[planning_type]['PL_BEG']
    end = settings.PLANNINGS[planning_type]['PL_END']

    planning_C = generate_days(beg, end, settings.SKIP_DAYS_C, settings.TURN, 'C')
    planning_D = generate_days(beg, end, settings.SKIP_DAYS_D, settings.TURN, 'D')
    planning_T = generate_days(beg, end, settings.SKIP_DAYS_T, settings.TURN, 'T')

    return {
        'C': planning_C,
        'D': planning_D,
        'T': planning_T
    }


def compute_slots(csv_inst_list, planning_type, empty_instructor=True, filter_uvs=None):
    # Filter by planning
    df = pd.read_csv(csv_inst_list)
    df = df.loc[df['Planning'] == planning_type]

    # Filter out when empty instructor
    if not empty_instructor:
        df = df.loc[(~pd.isnull(df['Intervenants']))]

    # Filter by set of UV
    if filter_uvs:
        df = df.loc[df['Code enseig.'].isin(filter_uvs)]

    planning = create_plannings(planning_type)

    planning_C = planning['C']
    pl_C = pd.DataFrame(planning_C)
    pl_C.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

    df_C = df.loc[df['Lib. créneau'].str.startswith('C'), :]
    df_Cm = pd.merge(df_C, pl_C, how='left', left_on='Jour', right_on='dayname')

    planning_D = planning['D']
    pl_D = pd.DataFrame(planning_D)
    pl_D.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

    df_D = df.loc[df['Lib. créneau'].str.startswith('D'), :]
    df_Dm = pd.merge(df_D, pl_D, how='left', left_on='Jour', right_on='dayname')

    planning_T = planning['T']
    pl_T = pd.DataFrame(planning_T)
    pl_T.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

    df_T = df.loc[df['Lib. créneau'].str.startswith('T'), :]
    if df_T['Semaine'].hasnans:
        df_Tm = pd.merge(df_T, pl_T, how='left', left_on='Jour', right_on='dayname')
    else:
        df_Tm = pd.merge(df_T, pl_T, how='left', left_on=['Jour', 'Semaine'], right_on=['dayname', 'semaine'])

    dfm = pd.concat([df_Cm, df_Dm, df_Tm], ignore_index=True)
    return dfm


def lib_list(lib):
    """Return a numeric tuple to sort course codenames"""
    m = re.match('([CDT])([0-9]*)([AB]*)', lib)
    crs = {'C': 0, 'D': 1, 'T': 2}[m.group(1)]
    no = int('0' + m.group(2))
    sem = 0 if m.group(3) == 'A' else 1
    return crs, no, sem


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
