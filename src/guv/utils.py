import hashlib
from pathlib import Path
import re
import string
import tempfile
from types import SimpleNamespace

import jinja2
import numpy as np
import pandas as pd
import unidecode

from .exceptions import CommonColumns, MissingColumns
from .logger import logger
from .translations import _, ngettext, get_localized_template_directories


def argument(*args, **kwargs):
    return SimpleNamespace(args=args, kwargs=kwargs)


def rotation_invariant_hash(s: str) -> str:
    # Generate all rotations
    rotations = [s[i:] + s[:i] for i in range(len(s))]

    # Get the lexicographically smallest rotation
    min_rotation = min(rotations)

    # Compute hash (e.g., SHA-256)
    return hashlib.sha256(min_rotation.encode()).hexdigest()


def slugrot_string(original: str) -> str:
    """Computes a rotation-invariant hash on a string.

    The process involves:
    - Unicode normalization
    - Lowercasing
    - Removing all whitespace
    - Applying rotation-invariant hashing
    """

    # Normalize Unicode characters (e.g., é -> e), and convert to lowercase
    normalized = unidecode.unidecode(original).lower()

    # Remove all whitespace characters
    compact = "".join(normalized.split())

    # Return the rotation-invariant hash
    return rotation_invariant_hash(compact)


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


def smart_cast(value):
    if isinstance(value, int):
        return value
    elif isinstance(value, float):
        if value.is_integer():
            return int(value)
        else:
            return value
    elif isinstance(value, str):
        try:
            int_val = int(value)
            return int_val
        except ValueError:
            try:
                float_val = float(value)
                return float_val
            except ValueError:
                return value
    else:
        return value


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
    def __init__(self, tmpl_dir):
        super().__init__(
            loader=jinja2.FileSystemLoader(tmpl_dir),
            extensions=['jinja2.ext.i18n'],
            block_start_string="((*",
            block_end_string="*))",
            variable_start_string="(((",
            variable_end_string=")))",
            comment_start_string="((=",
            comment_end_string="=))",
            trim_blocks=True,
            lstrip_blocks=True
        )
        self.install_gettext_callables(gettext=_, ngettext=ngettext)
        self.filters["escape_tex"] = escape_tex


def get_latex_template(template):
    dirs = get_localized_template_directories()
    latex_env = LaTeXEnvironment(dirs)
    return latex_env.get_template(template)


def get_template(template):
    dirs = get_localized_template_directories()
    env = jinja2.Environment(dirs)
    return env.get_template(template)


def render_latex_template(template, context):
    """Render template with context.

    Dictionary `context` must contain `filename_no_ext`. Return path
    to pdf file and rendered template.

    """

    tex = template.render(**context)
    temp_dir = tempfile.mkdtemp()
    filename_no_ext = context["filename_no_ext"]

    # Write tex
    tex_filepath = str(Path(temp_dir) / f"{filename_no_ext}.tex")
    with open(tex_filepath, "w") as fd:
        fd.write(tex)

    return tex_filepath


def normalize_string(name, type="excel"):
    if type == "excel":
        return name.replace("/", "")
    elif type == "file":
        name = re.sub(r"(?u)[^-\w. ]", "", name)
        if name in {"", ".", ".."}:
            raise ValueError(_("The identifier `{name}` does not allow for a valid filename").format(name=name))
        return name
    elif type == "file_no_space":
        name = re.sub(r"(?u)[^-_\w. ]", "", name)
        name = name.replace(" ", "_")
        if name in {"", ".", ".."}:
            raise ValueError(_("The identifier `{name}` does not allow for a valid filename").format(name=name))
        return name
    else:
        return TypeError("Unknown type", type)


def read_dataframe(filename, read_method=None, kw_read=None):
    """Read `filename` as a Pandas dataframe."""

    kw_read = kw_read or {}
    if read_method is None:
        if filename.endswith('.csv'):
            df = pd.read_csv(filename, **kw_read)
        elif filename.endswith('.xlsx'):
            df = pd.read_excel(filename, engine="openpyxl", **kw_read)
        elif filename.endswith('.xls'):
            import xlrd  # noqa: F401 - Needed for pandas engine
            df = pd.read_excel(filename, engine="xlrd", *kw_read)
        else:
            raise ValueError(_("Excel or CSV file only"))
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

    path_obj = Path(path)
    if not path_obj.is_absolute():
        return path

    # Check if path is a child of root_dir
    try:
        path_obj.relative_to(root_dir)
        # If we get here, it's a child - return relative to ref_dir
        return str(Path(path).relative_to(ref_dir))
    except ValueError:
        # Not a child of root_dir
        return path
