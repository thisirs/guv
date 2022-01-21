import os
import shutil
import time
import zipfile
from datetime import timedelta

import latex
import pandas as pd

from .config import logger, settings
from .exceptions import AbortWithBody, ImproperlyConfigured, NotUVDirectory
from .utils import render_latex_template


def rel_to_dir(path, root):
    if not os.path.isabs(path):
        return path

    if os.path.commonpath([settings.SEMESTER_DIR]) == os.path.commonpath(
        [settings.SEMESTER_DIR, path]
    ):
        return os.path.relpath(path, root)

    return path


def check_columns(dataframe, columns, **kwargs):
    """Vérifie que la ou les colonnes `columns` sont dans `dataframe`"""

    if "error_when" in kwargs:
        error_when = kwargs["error_when"]
    else:
        error_when = "not_found"

    if error_when not in ["exists", "not_found"]:
        raise Exception

    if isinstance(columns, str):
        columns = [columns]

    if error_when == "not_found":
        missing_cols = [c for c in columns if c not in dataframe.columns]

        if missing_cols:
            s = "s" if len(missing_cols) > 1 else ""
            missing_cols = ", ".join(f"`{e}`" for e in missing_cols)
            avail_cols = ", ".join(f"`{e}`" for e in dataframe.columns)
            if "file" in kwargs and "base_dir" in kwargs:
                fn = rel_to_dir(kwargs["file"], kwargs["base_dir"])
                msg = f"Colonne{s} manquante{s}: {missing_cols} dans le dataframe issu du fichier `{fn}`. Colonnes disponibles: {avail_cols}"
            else:
                msg = f"Colonne{s} manquante{s}: {missing_cols}. Colonnes disponibles: {avail_cols}"
            raise Exception(msg)
    else:
        common_cols = [c for c in columns if c in dataframe.columns]

        if common_cols:
            common_cols = ", ".join(f"`{e}`" for e in common_cols)
            s = "s" if len(common_cols) > 1 else ""
            if "file" in kwargs and "base_dir" in kwargs:
                msg = f"Colonne{s} déjà existante{s}: {common_cols} dans le dataframe issu du fichier `{fn}`."
            else:
                msg = f"Colonne{s} déjà existante{s}: {common_cols}"

            raise Exception(msg)


def selected_uv(all="dummy"):
    """Génère les UV configurées dans le fichier config.py du semestre."""

    if "SEMESTER" not in settings:
        raise NotUVDirectory("La tâche doit être exécutée dans un dossier d'UV/semestre")

    if settings.UV_DIR is not None:
        yield get_unique_uv()

    else:
        uv_to_planning = {
            uv: plng
            for plng, props in settings.PLANNINGS.items()
            for uv in props.get("UVS", []) + props.get("UES", [])
        }

        if not set(settings.UVS).issubset(set(uv_to_planning.keys())):
            raise ImproperlyConfigured("Des UVS n'ont pas de planning associé")

        for uv in settings.UVS:
            plng = uv_to_planning[uv]
            info = {
                "uv": uv,
                "planning": plng
            }
            yield plng, uv, info


def get_unique_uv():
    if "UV_DIR" in settings and settings.UV_DIR is not None:
        uv = os.path.basename(settings.UV_DIR)
        if uv not in settings.UVS:
            raise NotUVDirectory(
                f"Le dossier courant '{uv}' n'est pas reconnu en tant que "
                "dossier d'UV car il n'est pas enregistré dans la variable UVS."
            )

        plngs = [
            plng
            for plng, props in settings.PLANNINGS.items()
            if uv in props.get("UVS", []) + props.get("UES", [])
        ]

        if not plngs:
            raise ImproperlyConfigured("L'UV ne fait partie d'aucun planning")

        if len(plngs) >= 2:
            raise ImproperlyConfigured("L'UV fait partie de plusieurs plannings")

        plng = plngs[0]
        info = {"uv": uv, "planning": plng}
        return plng, uv, info
    else:
        raise NotUVDirectory("La tâche doit être exécutée dans un dossier d'UV")


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


def generate_days(beg, end, skip, turn, course_type):
    """Génére des tuples

    date, dayname, num, weekAB, numAB, nweek

    """

    if course_type not in ["C", "D", "T"]:
        raise Exception("Type de cours inconnu", course_type)

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
        dayname = turn[date] if date in turn else daynames[date.weekday()]
        day_counter[dayname] += 1
        num = day_counter[dayname]
        weekAB = None
        numAB = None

        if course_type == "T":
            # A, B, A, B when num is 1, 2, 3, 4
            weekAB = "A" if num % 2 == 1 else "B"

            # 1, 1, 2, 2 when num is 1, 2, 3, 4
            numAB = (num + 1) // 2

        yield date, dayname, num, weekAB, numAB, nweek


def create_plannings(planning_type):
    """Retourne trois dataframes Pandas avec les colonnes:

    - date: la date
    - dayname: le nom du jour (suivant TURN)
    - num: le numéro de la séance
    - weekAB: la semaine A ou B
    - numAB: le numéro de la séance avec prise en compte A/B
    - nweek: le numéro de la semaine

    Chaque ligne est un créneau dans le planning associé.
    """

    plannings = settings.PLANNINGS

    if planning_type not in plannings:
        raise Exception(
            f"Le planning `{planning_type}` n'est pas renseigné dans "
            "la variable `PLANNINGS` dans le fichier `config.py` du semestre."
        )

    props = settings.PLANNINGS[planning_type]

    if "PL_BEG" not in props:
        logger.warning(
            f"La clé `PL_BEG` est absente du planning `{planning_type}` dans la "
            "variable `PLANNINGS`, utilisation de la variable globale `PL_BEG`."
        )
        beg = settings.PL_BEG
    else:
        beg = props["PL_BEG"]

    if "PL_END" not in props:
        logger.warning(
            f"La clé `PL_END` est absente du planning `{planning_type}` dans la "
            "variable `PLANNINGS`, utilisation de la variable globale `PL_END`."
        )
        end = settings.PL_END
    else:
        end = props["PL_END"]

    if "TURN" not in props:
        logger.warning(
            f"La clé `TURN` est absente du planning `{planning_type}` dans la "
            "variable `PLANNINGS`, utilisation de la variable globale `TURN`."
        )
        turn = settings.TURN
    else:
        turn = props["TURN"]

    if "SKIP_DAYS_C" not in props:
        logger.warning(
            f"La clé `SKIP_DAYS_C` est absente du planning `{planning_type}` dans la "
            "variable `PLANNINGS`, utilisation de la variable globale `SKIP_DAYS_C`."
        )
        skip_days_c = settings.SKIP_DAYS_C
    else:
        skip_days_c = props["SKIP_DAYS_C"]

    if "SKIP_DAYS_D" not in props:
        logger.warning(
            f"La clé `SKIP_DAYS_D` est absente du planning `{planning_type}` dans la "
            "variable `PLANNINGS`, utilisation de la variable globale `SKIP_DAYS_D`."
        )
        skip_days_d = settings.SKIP_DAYS_D
    else:
        skip_days_d = props["SKIP_DAYS_D"]

    if "SKIP_DAYS_T" not in props:
        logger.warning(
            f"La clé `SKIP_DAYS_T` est absente du planning `{planning_type}` dans la "
            "variable `PLANNINGS`, utilisation de la variable globale `SKIP_DAYS_T`."
        )
        skip_days_t = settings.SKIP_DAYS_T
    else:
        skip_days_t = props["SKIP_DAYS_T"]

    planning_C = pd.DataFrame(
        generate_days(
            beg, end, skip_days_c, turn, "C"
        ),
        columns=["date", "dayname", "num", "weekAB", "numAB", "nweek"],
    )

    planning_D = pd.DataFrame(
        generate_days(
            beg, end, skip_days_d, turn, "D"
        ),
        columns=["date", "dayname", "num", "weekAB", "numAB", "nweek"],
    )

    planning_T = pd.DataFrame(
        generate_days(
            beg, end, skip_days_t, turn, "T"
        ),
        columns=["date", "dayname", "num", "weekAB", "numAB", "nweek"],
    )

    return planning_C, planning_D, planning_T


def compute_slots(csv_inst_list, planning_type, empty_instructor=True, filter_uvs=None):
    """Renvoie un dataframe de tous les créneaux horaires pour un planning défini.

    Le dataframe contient les colonnes :

    - Code enseig.
    - Activité
    - Jour
    - Heure début
    - Heure fin
    - Semaine
    - Locaux
    - Lib. créneau
    - Planning
    - Responsable enseig.
    - Intervenants
    - Responsable
    - date
    - dayname
    - num
    - weekAB
    - numAB
    - nweek

    """

    # Filter by planning
    df = pd.read_csv(csv_inst_list)
    df = df.loc[df["Planning"] == planning_type]

    # Filter out when empty instructor
    if not empty_instructor:
        df = df.loc[(~pd.isnull(df["Intervenants"]))]

    # Filter by set of UV
    if filter_uvs:
        df = df.loc[df["Code enseig."].isin(filter_uvs)]

    # List of days for all course type
    pl_C, pl_D, pl_T = create_plannings(planning_type)

    df_C = df.loc[df["Lib. créneau"].str.startswith("C"), :]
    df_Cm = pd.merge(df_C, pl_C, how="left", left_on="Jour", right_on="dayname")

    df_D = df.loc[df["Lib. créneau"].str.startswith("D"), :]
    df_Dm = pd.merge(df_D, pl_D, how="left", left_on="Jour", right_on="dayname")

    df_T = df.loc[df["Lib. créneau"].str.startswith("T"), :]
    if df_T["Semaine"].hasnans:
        df_Tm = pd.merge(df_T, pl_T, how="left", left_on="Jour", right_on="dayname")
    else:
        df_Tm = pd.merge(
            df_T,
            pl_T,
            how="left",
            left_on=["Jour", "Semaine"],
            right_on=["dayname", "weekAB"],
        )

    dfm = pd.concat([df_Cm, df_Dm, df_Tm], ignore_index=True)
    return dfm


def render_from_contexts(template, contexts, save_tex=False, target=None):
    """Render `template` with different `contexts` and save using `target`.

    Rendered in a temporary directory by `render_latex_template`.
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

