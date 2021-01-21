import os
import re
import string
import hashlib
import textwrap
from types import SimpleNamespace
from datetime import timedelta
from schema import Schema, Or, And, Use
import pandas as pd
import numpy as np
import jinja2
import unidecode

import doit_utc


def rel_to_dir(path, root):
    common_prefix = os.path.commonprefix([path, root])
    return os.path.relpath(path, common_prefix)


def check_columns(dataframe, columns, **kwargs):
    """Vérifie que la ou les colonnes `columns` sont dans `dataframe`"""

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


def fillna_column(colname, na_value=None, group_column=None):
    """Renvoie une fonction qui remplace les valeurs non définies dans la
    colonne `colname`. Une seule des options `na_value` et
    `group_column` doit être spécifiée. Si `na_value` est spécifiée,
    on remplace inconditionnellement par la valeur fournie. Si
    `group_column` est spécifiée, on complète en groupant par
    `group_column` en prenant la seule valeur valide par groupe dans
    cette colonne.

    Utilisable avec l'argument `postprocessing` ou `preprocessing`
    dans la fonction `aggregate` ou directement à la place de la
    fonction `aggregate` dans `AGGREGATE_DOCUMENTS`.

    Exemples :
    > fillna_column("group", na_value="ABS")
    > fillna_column("group", group_column="choix")

    """
    if not((na_value is None) ^ (group_column is None)):
        raise Exception("Une seule option doit être spécifiée")

    if na_value is not None:
        def func(df, path=None):
            check_columns(df, [colname])
            df[colname].fillna(na_value, inplace=True)
            return df

        func.__name__ = f"Fill NA in column `{colname}` with `{na_value}`"

    else:
        def fill_by_group(g):
            idx_first = g[colname].first_valid_index()
            idx_last = g[colname].last_valid_index()
            if idx_first is not None:
                if idx_first == idx_last:
                    g[colname] = g.loc[idx_first, colname]
                else:
                    raise Exception("Plusieurs valeurs non-NA dans le groupe")
            return g

        def func(df, path=None):
            check_columns(df, [colname, group_column])
            return df.groupby(group_column).apply(fill_by_group)

        func.__name__ = f"Fill NA in column `{colname}` by `{group_column}`"

    return func


def replace_regex(colname, *reps, new_colname=None):
    """Renvoie une fonction qui remplace les occurrences de toutes les
    expressions régulières renseignées dans `reps` dans la colonne
    `colname`.

    Utilisable avec l'argument `postprocessing` ou `preprocessing`
    dans la fonction `aggregate` ou directement à la place de la
    fonction `aggregate` dans `AGGREGATE_DOCUMENTS`.

    Par exemple :
    > replace_regex("group", (r"group([0-9])", r"G\1"), (r"g([0-9])", r"G\1"))

    """

    def func(df, path=None):
        check_columns(df, colname)
        s = df[colname].copy()
        for rep in reps:
            s = s.str.replace(*rep, regex=True)
        cn = new_colname if new_colname is not None else colname
        df = df.assign(**{cn: s})
        return df

    func.__name__ = f"Regex replacements in column `{colname}`"
    return func


def replace_column(colname, rep_dict, new_colname=None):
    """Renvoie une fonction qui remplace les valeurs exactes renseignées
    dans `rep_dict` dans la colonne `colname`.

    Utilisable avec l'argument `postprocessing` ou `preprocessing`
    dans la fonction `aggregate` ou directement à la place de la
    fonction `aggregate` dans `AGGREGATE_DOCUMENTS`.

    Exemple :
    > replace_column("group", {"TD 1": "TD1", "TD 2": "TD2"})

    """

    def func(df, path=None):
        check_columns(df, colname)
        col_ref = df[colname].replace(rep_dict)
        cn = new_colname if new_colname is not None else colname
        df = df.assign(**{cn: col_ref})
        return df

    func.__name__ = f"Replacements in column `{colname}`"

    return func


def aggregate(left_on, right_on, preprocessing=None, postprocessing=None, subset=None, drop=None, rename=None, read_method=None, kw_read={}):
    """Renvoie une fonction qui réalise l'agrégation d'un DataFrame avec
    un fichier.

    Les arguments `left_on` et `right_on` sont les clés pour réaliser
    une jointure : `left_on` est la clé du DataFrame existant et
    `right_on` est la clé du DataFrame à agréger présent dans le
    fichier. `subset` est une liste des colonnes à garder, `drop` une
    liste des colonnes à enlever. `rename` est un dictionnaire des
    colonnes à renommer. `read_method` est un callable appelé avec
    `kw_read` pour lire le fichier contenant le DataFrame à agréger.
    `preprocessing` et `postprocessing` sont des callable qui prennent
    en argument un DataFrame et en renvoie un et qui réalise un pré ou
    post traitement sur l'agrégation.

    """

    def aggregate0(left_df, path):
        nonlocal left_on, right_on, subset, drop, rename

        # Columns that will be removed after merging
        drop_cols = []

        # Flag if left_on is a computed column
        left_on_is_added = False

        # Add column if callable, callable should return of pandas
        # Series
        if callable(left_on):
            left_on = left_on(left_df)
            left_df = left_df.assign(**{left_on.name: left_on.values})
            left_on = left_on.name
            left_on_is_added = True

        # Check if it exists
        if isinstance(left_on, str):
            # Check that left_on column exists
            check_columns(left_df, left_on)
        else:
            raise Exception("L'argument 'left_on' doit être un callable ou une chaine de caractères")

        # Infer a read method if not provided
        if read_method is None:
            if path.endswith('.csv'):
                right_df = pd.read_csv(path, **kw_read)
            elif path.endswith('.xlsx') or path.endswith('.xls'):
                right_df = pd.read_excel(path, engine="openpyxl", **kw_read)
            else:
                raise Exception('No read method and unsupported file extension')
        else:
            right_df = read_method(path, **kw_read)

        if preprocessing is not None:
            if hasattr(preprocessing, "__name__"):
                print(f"Preprocessing: {preprocessing.__name__}")
            else:
                print("Preprocessing")
            right_df = preprocessing(right_df)

        # Add column if callable
        if callable(right_on):
            right_on = right_on(right_df)
            right_df = right_df.assign(**{right_on.name: right_on.values})
            right_on = right_on.name

        # Check if it exists
        if isinstance(right_on, str):
            check_columns(right_df, right_on)
        else:
            raise Exception("Unsupported type for right_on")

        # Extract subset of columns, right_on included
        if subset is not None:
            sc_columns = Or(*right_df.columns)
            subset = Schema(Or(And(sc_columns, Use(lambda x: [x])), [sc_columns])).validate(subset)
            subset0 = list({s: 1 for s in [right_on] + subset}.keys())
            right_df = right_df[subset0]

        # Allow to drop columns, right_on not allowed
        if drop is not None:
            sc_columns = Or(*right_df.columns)
            drop = Schema(Or(And(sc_columns, Use(lambda x: [x])), [sc_columns])).validate(drop)
            if right_on in drop:
                raise Exception('On enlève pas la clé')
            right_df = right_df.drop(drop, axis=1)

        # Rename columns in data to be merged
        if rename is not None:
            if right_on in rename:
                raise Exception('Pas de renommage de la clé possible')
            rename = Schema({str: str}).validate(rename)
            right_df = right_df.rename(columns=rename)

        # Columns to drop after merge: primary key of right dataframe
        # only if name is different, _merge column added by pandas
        # during merge, programmatically added column is
        # left_on_is_added is set
        drop_cols = ['_merge']
        if right_on != left_on:
            if right_on in left_df.columns:
                drop_cols += [right_on + "_y"]
            else:
                drop_cols += [right_on]

        if left_on_is_added:
            drop_cols += [left_on]

        # Record same column name between right_df and left_df to
        # merge them eventually
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
        key = right_on
        if (right_on != left_on and right_on in left_df.columns):
            key = key + "_y"

        for index, row in merged_df_ro.iterrows():
            print("WARNING: identifiant présent dans le document à aggréger mais introuvable dans la base de données :", row[key])

        if postprocessing is not None:
            if hasattr(postprocessing, "__name__"):
                print(f"Postprocessing: {postprocessing.__name__}")
            else:
                print("Postprocessing")
            agg_df = postprocessing(agg_df)

        # Try to merge columns
        for c in duplicated_columns:
            c_y = c + '_y'
            print("Trying to merge columns '%s' and '%s'..." % (c, c_y), end='')
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


def argument(*args, **kwargs):
    return SimpleNamespace(args=args, kwargs=kwargs)


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
    """Renvoie une fonction d'agrégation d'un fichier .org à utiliser dans
AGGREGATE_DOCUMENTS.
    """

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


def make_groups(collection, proportions):
    n = len(collection)
    n_groups = len(proportions)

    # Array that sum to one
    proportions = np.array(proportions)
    proportions = proportions / sum(proportions)

    # Rough frequency
    frequency = np.floor(n * proportions).astype(int)

    # Add remaining items
    order = np.argsort(frequency)
    rest = n - sum(frequency)
    frequency[order[:rest]] += 1

    assert(sum(frequency) == n)
    assert(len(frequency) == n_groups)

    groups = []
    cs = np.concatenate(([0], np.cumsum(frequency)))
    for i in range(len(cs)-1):
        groups.append(collection[cs[i]:cs[i+1]])

    return groups


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


class LaTeXEnvironment(jinja2.Environment):
    def __init__(self):
        tmpl_dir = os.path.join(doit_utc.__path__[0], "templates")
        super().__init__(
            loader=jinja2.FileSystemLoader(tmpl_dir),
            block_start_string="((*",
            block_end_string="*))",
            variable_start_string="(((",
            variable_end_string=")))",
            comment_start_string="((=",
            comment_end_string="=))",
        )
        self.filters["escape_tex"] = escape_tex
