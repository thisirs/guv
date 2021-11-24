import os
import time
import zipfile
import shutil
from datetime import timedelta
import pandas as pd
import latex

from .exceptions import NotUVDirectory, ImproperlyConfigured, SkipWithBody
from .utils import rel_to_dir, render_latex_template
from .config import settings, logger


def selected_uv(all="dummy"):
    "Génère les UV configurées dans le fichier config.py du semestre"

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
        uv = settings.UV_DIR
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


class Output():
    def __init__(self, target, protected=False):
        self._target = target
        self.protected = protected
        self.choice = None

    def __enter__(self):
        if os.path.exists(self._target):
            if self.protected:
                while True:
                    try:
                        self.choice = input('Le fichier `%s'' existe déjà. Écraser (d), garder (g), sauvegarder (s), annuler (a) ? ' % rel_to_dir(self._target, settings.SEMESTER_DIR))
                        if self.choice not in ["d", "g", "s", "a"]:
                            raise ValueError

                        if self.choice == 'd':
                            os.remove(self._target)
                        elif self.choice == 's':
                            parts = os.path.splitext(self._target)
                            timestr = time.strftime("_%Y%m%d-%H%M%S")
                            target0 = parts[0] + timestr + parts[1]
                            os.rename(self._target, target0)
                    except ValueError:
                        continue
                    else:
                        break
            else:
                print('Écrasement du fichier `%s`' %
                      rel_to_dir(self._target, settings.SEMESTER_DIR))
        else:
            dirname = os.path.dirname(self._target)
            if not os.path.exists(dirname):
                os.makedirs(dirname)

        return self

    def _maybe_cancel(self):
        if self.choice == "g":
            raise SkipWithBody
        if self.choice == "a":
            raise Exception("Annulation")

    @property
    def target(self):
        self._maybe_cancel()
        return self._target

    def __exit__(self, type, value, traceback):
        if type is SkipWithBody:
            self.result = "keep"
            return True
        if type is None:
            self.result = "write"
            print(f"Écriture du fichier `{rel_to_dir(self.target, settings.SEMESTER_DIR)}`")
            return

        self.result = "cancel"
        return


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

    planning_C = pd.DataFrame(
        generate_days(
            beg, end, settings.SKIP_DAYS_C, settings.TURN, "C"
        ),
        columns=["date", "dayname", "num", "weekAB", "numAB", "nweek"],
    )

    planning_D = pd.DataFrame(
        generate_days(
            beg, end, settings.SKIP_DAYS_D, settings.TURN, "D"
        ),
        columns=["date", "dayname", "num", "weekAB", "numAB", "nweek"],
    )

    planning_T = pd.DataFrame(
        generate_days(
            beg, end, settings.SKIP_DAYS_T, settings.TURN, "T"
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
    pdfs = []
    texs = []
    for context in contexts:
        try:
            filepath, tex_filepath = render_latex_template(template, context)
        except latex.exc.LatexBuildError as e:
            logger.warning("LaTeX build failed", e)
            continue
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

