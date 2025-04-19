import datetime
import hashlib
import os
import re
import string
import tempfile
from types import SimpleNamespace

import jinja2
import latex
import numpy as np
import pandas as pd
import unidecode

import guv

from .exceptions import CommonColumns, MissingColumns
from .logger import logger


def argument(*args, **kwargs):
    return SimpleNamespace(args=args, kwargs=kwargs)


def hexxor(a, b):  # xor two hex strings of the same length
    return "".join(["%x" % (int(x, 16) ^ int(y, 16)) for (x, y) in zip(a, b)])


def md5(fname):
    hash_md5 = hashlib.md5()
    hash_md5.update(fname.encode('utf8'))
    return hash_md5.hexdigest()


def hash_rot_md5(a):
    """Return a hash invariant by rotation"""

    b = a + a
    subseqs = np.unique(np.array([b[i : (i + len(a))] for i in range(len(a))]))
    s0 = "0" * len(a)
    s0 = md5(s0)
    for s in subseqs:
        s0 = hexxor(s0, md5(s))

    return s0


def slugrot_string(e):
    """Rotation-invariant hash on a string"""

    e0 = unidecode.unidecode(e).lower()
    e0 = ''.join(e0.split())
    return hash_rot_md5(e0)


def split_codename(lib):
    """Return a numeric tuple to sort course codenames"""
    m = re.match('([CDT])([0-9]*)([AB]*)', lib)
    crs = {'C': 0, 'D': 1, 'T': 2}[m.group(1)]
    no = int('0' + m.group(2))
    sem = 0 if m.group(3) == 'A' else 1
    return crs, no, sem


def score_codenames(slot_names):
    """Renvoie un tuple comptant les types de cours Cours/TD/TP"""

    if isinstance(slot_names, str):
        slot_names = [slot_names]

    C_slots = sorted([slot_name for slot_name in slot_names if re.search("C[0-9]*", slot_name)])
    D_slots = sorted([slot_name for slot_name in slot_names if re.search("D[0-9]*", slot_name)])
    T_slots = sorted([slot_name for slot_name in slot_names if re.search("T[0-9]*([AB])?", slot_name)])

    return (- len(C_slots), "empty" if len(C_slots) == 0 else C_slots[0],
            - len(D_slots), "empty" if len(D_slots) == 0 else D_slots[0],
            - len(T_slots), "empty" if len(T_slots) == 0 else T_slots[0])


def convert_author(author):
    if isinstance(author, str):
        parts = re.split('[ -]', author)
        return ''.join(e[0].upper() for e in parts)
    else:
        return ''


def convert_to_time(value):
    if isinstance(value, datetime.time):
        return value
    elif isinstance(value, datetime.datetime):
        return value.time()
    else:
        try:
            return datetime.datetime.strptime(value, "%H:%M").time()
        except ValueError:
            return datetime.datetime.strptime(value, "%H:%M:%S").time()


def convert_to_numeric(series):
    try:
        return pd.to_numeric(series)
    except ValueError:
        pass
    try:
        return pd.to_numeric(series.str.replace(",", "."))
    except ValueError:
        pass

    raise ValueError


def plural(num, plural, singular):
    if num > 1:
        return plural
    else:
        return singular


def ps(num):
    return plural(num, "s", "")


def px(num):
    return plural(num, "x", "")


class FormatDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def pformat(s, **kwargs):
    formatter = string.Formatter()
    mapping = FormatDict(**kwargs)
    return formatter.vformat(s, (), mapping)


def make_groups(n, proportions):
    """Renvoie une partition en groupes de `collection` guidées par `proportions`.

    La longueur de `proportions` fixe le nombre de groupes et la
    valeur correspondante est la taille du groupe en proportion. Par
    exemple, `[1, 1, 1]` correspond à trois groupes de même taille. Les
    groupes sont constitués de manière contiguë.

    """

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

    return np.repeat(np.arange(n_groups), frequency)


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


def generate_groupby(df, key, ascending=None):
    """Generate sub-dataframes by grouping by `key` in `df`."""

    if key is not None:
        groups = dict(list(df.groupby(key)))
        keys = groups.keys()
        if ascending is not None:
            keys = sorted(keys, reverse=not ascending)

        for key in keys:
            yield key, groups[key]
    else:
        yield None, df


LATEX_SUBS = (
    (re.compile(r'\\'), r'\\textbackslash'),
    (re.compile(r'([{}_#%&$])'), r'\\\1'),
    (re.compile(r'~'), r'\~{}'),
    (re.compile(r'\^'), r'\^{}'),
    (re.compile(r'"'), r"''"),
    (re.compile(r'\.\.\.+'), r'\\ldots'))


def escape_tex(value):
    if value is None:
        return "None"
    newval = value
    for pattern, replacement in LATEX_SUBS:
        newval = pattern.sub(replacement, newval)
    return newval


class LaTeXEnvironment(jinja2.Environment):
    def __init__(self):
        tmpl_dir = os.path.join(guv.__path__[0], "data", "templates")
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


def render_latex_template(template, context):
    """Render template with context.

    Dictionary `context` must contain `filename_no_ext`. Return path
    to pdf file and rendered template.

    """

    latex_env = LaTeXEnvironment()
    tmpl = latex_env.get_template(template)

    tex = tmpl.render(**context)
    temp_dir = tempfile.mkdtemp()
    filename_no_ext = context["filename_no_ext"]

    # Write tex
    tex_filepath = os.path.join(temp_dir, filename_no_ext + ".tex")
    with open(tex_filepath, "w") as fd:
        fd.write(tex)

    return tex_filepath


def compile_latex_file(tex_file):
    # Write pdf
    pdf = latex.build_pdf(open(tex_file))
    pdf_file = os.path.splitext(tex_file)[0] + ".pdf"
    pdf.save_to(pdf_file)

    return pdf_file


def normalize_string(name, type="excel"):
    if type == "excel":
        return name.replace("/", "")
    elif type == "file":
        name = re.sub(r"(?u)[^-\w. ]", "", name)
        if name in {"", ".", ".."}:
            raise ValueError(f"L'identifiant `{name}` ne permet pas d'avoir un nom de fichier valide")
        return name
    elif type == "file_no_space":
        name = re.sub(r"(?u)[^-_\w. ]", "", name)
        name = name.replace(" ", "_")
        if name in {"", ".", ".."}:
            raise ValueError(f"L'identifiant `{name}` ne permet pas d'avoir un nom de fichier valide")
        return name
    else:
        return TypeError("Unknown type", type)


def read_dataframe(filename, read_method=None, kw_read=None):
    """Read `filename` as a Pandas dataframe."""

    kw_read = kw_read or {}
    if read_method is None:
        if filename.endswith('.csv'):
            df = pd.read_csv(filename, **kw_read)
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(filename, engine="openpyxl", **kw_read)
        else:
            raise ValueError("Fichier Excel ou csv seulement")
    else:
        df = read_method(filename, **kw_read)

    return df


def check_if_absent(dataframe, columns, errors="raise"):
    if errors not in ("raise", "warning", "silent"):
        raise ValueError("Unknown `errors`", errors)

    if isinstance(columns, str):
        columns = [columns]

    common_cols = [c for c in columns if c in dataframe.columns]
    if common_cols:
        e = CommonColumns(common_cols)
        if errors == "raise":
            raise e
        elif errors == "warning":
            logger.warning(str(e))
        elif errors == "silent":
            pass
        else:
            raise ValueError("Unknown `errors`", errors)

    return not common_cols


def check_if_present(dataframe, columns, errors="raise"):
    if errors not in ("raise", "warning", "silent"):
        raise ValueError("Unknown `errors`", errors)

    if isinstance(columns, str):
        columns = [columns]

    missing_cols = [c for c in columns if c not in dataframe.columns]
    if missing_cols:
        e = MissingColumns(missing_cols, dataframe.columns)
        if errors == "raise":
            raise e
        elif errors == "warning":
            logger.warning(str(e))
        elif errors == "silent":
            pass
        else:
            raise ValueError("Unknown `errors`", errors)

    return not missing_cols


def rel_to_dir_aux(path, ref_dir, root_dir):
    """Maybe make `path` relative to `ref_dir` if absolute and child of `root_dir`"""

    if not os.path.isabs(path):
        return path

    if os.path.commonpath([root_dir]) == os.path.commonpath([root_dir, path]):
        return os.path.relpath(path, ref_dir)

    return path
