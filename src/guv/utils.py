import hashlib
import os
import re
import string
import tempfile
from types import SimpleNamespace

import jinja2
import latex
import numpy as np
import unidecode

import guv

from .exceptions import ImproperlyConfigured


def check_filename(filename):
    if not os.path.exists(filename):
        raise ImproperlyConfigured("Le fichier `{filename}` n'existe pas")


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


def score_codenames(libs):
    """Renvoie un tuple comptant les types de cours Cours/TD/TP"""

    sc = [0, 0, 0]
    mapping = {'C': 0, 'D': 1, 'T': 2}
    for lib in libs:
        m = re.search('([CDT])[0-9]*([AB]?)', lib)
        if m:
            ix = mapping[m.group(1)]
            if m.group(2):
                sc[ix] += .5
            else:
                sc[ix] += 1
        else:
            raise Exception(f"L'identifiant {lib} n'est pas matché")
    return tuple(sc)


class FormatDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def pformat(s, **kwargs):
    formatter = string.Formatter()
    mapping = FormatDict(**kwargs)
    return formatter.vformat(s, (), mapping)


def make_groups(collection, proportions):
    """Renvoie une partition en groupes de `collection` guidées par `proportions`.

    La longueur de `proportions` fixe le nombre de groupes et la
    valeur correspondante est la taille du groupe en proportion. Par
    exemple, `[1, 1, 1]` correspond à trois groupes de même taille. Les
    groupes sont constitués de manière contigue.

    """

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


def generate_groupby(df, key):
    """Generate sub-dataframes by grouping by `key` in `df`."""

    if key is not None:
        for title, group in df.groupby(key):
            yield title, group
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
        tmpl_dir = os.path.join(guv.__path__[0], "templates")
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

    Dictionnary `context` must contain `filename_no_ext`. Return path
    to pdf file and rendered template.

    """

    latex_env = LaTeXEnvironment()
    tmpl = latex_env.get_template(template)

    tex = tmpl.render(**context)
    temp_dir = tempfile.mkdtemp()
    filename_no_ext = context["filename_no_ext"]

    # Write pdf
    pdf = latex.build_pdf(tex)
    filepath = os.path.join(temp_dir, filename_no_ext + ".pdf")
    pdf.save_to(filepath)

    # Write tex
    tex_filepath = os.path.join(temp_dir, filename_no_ext + ".tex")
    with open(tex_filepath, "w") as fd:
        fd.write(tex)

    return filepath, tex_filepath


