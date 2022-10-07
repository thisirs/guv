from collections import defaultdict
import os
import shutil
import time
import zipfile
from datetime import timedelta

from .config import settings
from .exceptions import AbortWithBody, ImproperlyConfigured, NotUVDirectory
from .logger import logger
from .utils import render_latex_template


def rel_to_dir(path, root):
    if not os.path.isabs(path):
        return path

    if os.path.commonpath([settings.SEMESTER_DIR]) == os.path.commonpath(
        [settings.SEMESTER_DIR, path]
    ):
        return os.path.relpath(path, root)

    return path


def check_filename(filename, **kwargs):
    if not os.path.exists(filename):
        fn = rel_to_dir(filename, kwargs["base_dir"])
        raise ImproperlyConfigured(f"Le fichier `{fn}` n'existe pas")


def ensure_absent_columns(dataframe, columns, errors="raise", file=None, base_dir=None):
    if errors not in ("raise", "warning", "silent"):
        raise ValueError("invalid error value specified")

    if isinstance(columns, str):
        columns = [columns]

    common_cols = [c for c in columns if c in dataframe.columns]

    if common_cols:
        s = "s" if len(common_cols) > 1 else ""
        common_cols = ", ".join(f"`{e}`" for e in common_cols)
        if file is not None and base_dir is not None:
            fn = rel_to_dir(file, base_dir)
            msg = f"Colonne{s} déjà existante{s}: {common_cols} dans le dataframe issu du fichier `{fn}`."
        else:
            msg = f"Colonne{s} déjà existante{s}: {common_cols}"

        if errors == "raise":
            raise Exception(msg)
        if errors == "warning":
            logger.warning(msg)

    return not not common_cols


def ensure_present_columns(dataframe, columns, errors="raise", file=None, base_dir=None):
    if errors not in ("raise", "warning", "silent"):
        raise ValueError("invalid error value specified")

    if isinstance(columns, str):
        columns = [columns]

    missing_cols = [c for c in columns if c not in dataframe.columns]

    if missing_cols:
        s = "s" if len(missing_cols) > 1 else ""
        missing_cols = ", ".join(f"`{e}`" for e in missing_cols)
        avail_cols = ", ".join(f"`{e}`" for e in dataframe.columns)
        if file is not None and base_dir is not None:
            fn = rel_to_dir(file, base_dir)
            msg = f"Colonne{s} manquante{s}: {missing_cols} dans le dataframe issu du fichier `{fn}`. Colonnes disponibles: {avail_cols}"
        else:
            msg = f"Colonne{s} manquante{s}: {missing_cols}. Colonnes disponibles: {avail_cols}"

        if errors == "raise":
            raise Exception(msg)
        if errors == "warning":
            logger.warning(msg)

    return not not missing_cols


def configured_uv(uvs):
    # Collect uv to plannings in PLANNINGS
    uv2plannings = defaultdict(list)
    for plng, props in settings.PLANNINGS.items():
        if "UVS" not in props and "UES" not in props:
            raise ImproperlyConfigured(f"Le planning `{plng}` n'a pas de clé `UVS` ou `UES`.")
        for uv in props.get("UVS", []) + props.get("UES", []):
            uv2plannings[uv].append(plng)

    for uv in uvs:
        # Check that all uv are in UVS
        if uv not in settings.UVS:
            raise NotUVDirectory(
                f"L'UV `{uv}` n'est pas reconnue car elle n'est pas enregistrée dans la variable `UVS`."
            )

        # Check that UV directory exists
        if not os.path.exists(os.path.join(settings.SEMESTER_DIR, uv)):
            raise ImproperlyConfigured(
                f"Le dossier pour l'UV {uv} n'existe pas."
            )

        if uv not in uv2plannings:
            raise ImproperlyConfigured(f"L'UV `{uv}` n'a pas de planning associé dans `PLANNINGS`")

        plannings = uv2plannings[uv]
        if len(plannings) > 1:
            raise ImproperlyConfigured(f"L'UV `{uv}` a plusieurs plannings associés dans `PLANNINGS`")

        yield [plannings[0], uv, {"uv": uv, "planning": plannings[0]}]


def selected_uv():
    """Génère les UV configurées dans le fichier config.py du semestre suivant le dossier courant."""

    if "SEMESTER" not in settings:
        raise NotUVDirectory("La tâche doit être exécutée dans un dossier d'UV/semestre")

    if settings.UV_DIR is not None:
        yield get_unique_uv()
        return

    uvs = settings.UVS
    yield from configured_uv(uvs)


def get_unique_uv():
    """Return only one UV if in UV directory."""

    if "UV_DIR" not in settings or settings.UV_DIR is None:
        raise NotUVDirectory("La tâche doit être exécutée dans un dossier d'UV")

    uv = os.path.basename(settings.UV_DIR)
    conf_uvs = configured_uv([uv])

    return list(conf_uvs)[0]


def ask_choice(prompt, choices={}):
    while True:
        try:
            choice = input(prompt)
            if choice not in choices.keys():
                raise ValueError
        except ValueError:
            continue
        else:
            break

    return choices[choice]


class Output:
    def __init__(self, target, protected=False):
        self._target = target
        self.protected = protected
        self.action = None

    def __enter__(self):
        if os.path.exists(self._target):
            if self.protected:
                self.action = ask_choice(
                    f"Le fichier `{rel_to_dir(self._target, settings.SEMESTER_DIR)}` existe déjà. "
                    "Écraser (d), garder (g), sauvegarder (s), annuler (a) ? ",
                    choices={
                        "d": "overwrite",
                        "g": "keep",
                        "s": "backup",
                        "a": "abort",
                    },
                )
            else:
                self.action = "overwrite"
        else:
            self.action = "write"

        return self

    def _prepare(self):
        if self.action == "abort":
            raise Exception("Annulation")
        if self.action == "keep":
            raise AbortWithBody
        if self.action == "backup":
            parts = os.path.splitext(self._target)
            timestr = time.strftime("_%Y%m%d-%H%M%S")
            target0 = parts[0] + timestr + parts[1]
            os.rename(self._target, target0)
            logger.info("Sauvegarde vers `%s`", rel_to_dir(target0, settings.CWD))
        elif self.action == "overwrite":
            logger.info("Écrasement du fichier `%s`", rel_to_dir(self._target, settings.CWD))
        elif self.action == "write":
            dirname = os.path.dirname(self._target)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            logger.info("Écriture du fichier `%s`", rel_to_dir(self._target, settings.CWD))

    @property
    def target(self):
        self._prepare()
        return self._target

    def __exit__(self, type, value, traceback):
        if type is None:
            return
        if type is AbortWithBody:
            return True
        if issubclass(type, Exception):
            return False


def generate_row(beg, end, skip, turn):
    """Generate tuples that represent days."""

    daynames = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
    delta = end - beg
    day_counter = {day: 0 for day in daynames}

    nweek = 0

    for i in range(delta.days + 1):
        date = beg + timedelta(days=i)

        # Lundi
        if i % 7 == 0:
            nweek += 1

        # Ignore week-end
        if date.weekday() in [5, 6]:
            continue

        # Skip days
        if date in skip:
            continue

        # Get real day
        dayname = turn[date].capitalize() if date in turn else daynames[date.weekday()]
        if dayname not in daynames:
            daynames_ = ", ".join(f"`{d}`" for d in daynames)
            raise ImproperlyConfigured(
                f"Nom de journée inconnu: `{dayname}`. Choisir parmi {daynames_}"
            )
        day_counter[dayname] += 1
        num = day_counter[dayname]

        # A, B, A, B when num is 1, 2, 3, 4
        weekAB = "A" if num % 2 == 1 else "B"

        # 1, 1, 2, 2 when num is 1, 2, 3, 4
        numAB = (num + 1) // 2

        yield date, dayname, num, weekAB, numAB, nweek


def render_from_contexts(template, contexts, save_tex=False, target=None):
    """Render `template` with different `contexts` and save using `target`.

    Rendered in a temporary directory by `render_latex_template`.
    `target` should be a name without extension. A zip of pdf
    extension will be added.

    """

    pdfs = []
    texs = []
    for context in contexts:
        filepath, tex_filepath = render_latex_template(template, context)
        pdfs.append(filepath)
        texs.append(tex_filepath)

    # Écriture du pdf dans un zip si plusieurs
    if len(pdfs) == 1:
        with Output(target + ".pdf") as out:
            shutil.move(pdfs[0], out.target)
    else:
        with Output(target + ".zip") as out:
            with zipfile.ZipFile(out.target, "w") as z:
                for filepath in pdfs:
                    z.write(filepath, os.path.basename(filepath))

    # Écriture du tex dans un zip si plusieurs
    if save_tex:
        if len(texs) == 1:
            with Output(target + ".tex") as out:
                shutil.move(texs[0], out.target)
        else:
            with Output(target + "_source.zip") as out:
                with zipfile.ZipFile(out.target, "w") as z:
                    for filepath in texs:
                        z.write(filepath, os.path.basename(filepath))

