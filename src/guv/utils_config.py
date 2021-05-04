import os
import time
from datetime import timedelta
import pandas as pd

from .exceptions import NotUVDirectory, ImproperlyConfigured
from .utils import rel_to_dir, check_columns
from .config import settings, logger


def selected_uv(all="dummy"):
    "Génère les UV configurées dans le fichier config.py du semestre"

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
    if settings.UV_DIR is not None:
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
        self.target = target
        self.protected = protected

    def __enter__(self):
        if os.path.exists(self.target):
            if self.protected:
                while True:
                    try:
                        choice = input('Le fichier `%s'' existe déjà. Écraser (d), garder (g), sauvegarder (s), annuler (a) ? ' % rel_to_dir(self.target, settings.SEMESTER_DIR))
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
                      rel_to_dir(self.target, settings.SEMESTER_DIR))
        else:
            dirname = os.path.dirname(self.target)
            if not os.path.exists(dirname):
                os.makedirs(dirname)

        return lambda: self.target

    def __exit__(self, type, value, traceback):
        if type is ZeroDivisionError:
            return True
        if type is None:
            print(f"Wrote `{rel_to_dir(self.target, settings.SEMESTER_DIR)}'")


def create_plannings(planning_type):
    """Generate list of working days according to planning"""

    def generate_days(beg, end, skip, turn, course):
        """Generate working days from BEG to END"""

        daynames = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
        delta = end - beg
        semaine = {day: 0 for day in daynames}

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
            if course == "T":
                sem = "A" if semaine[day] % 2 == 0 else "B"
                numAB = semaine[day] // 2 + 1
                semaine[day] += 1
                num = semaine[day]
            elif course in ["C", "D"]:
                semaine[day] += 1
                numAB = None
                sem = None
                num = semaine[day]
            else:
                raise Exception("course inconnu")

            if d in turn:
                yield d, turn[d], sem, num, numAB, nweek
            else:
                yield d, daynames[d.weekday()], sem, num, numAB, nweek

    beg = settings.PLANNINGS[planning_type]["PL_BEG"]
    end = settings.PLANNINGS[planning_type]["PL_END"]

    planning_C = pd.DataFrame(
        generate_days(
            beg, end, settings.SKIP_DAYS_C, settings.TURN, "C"
        ),
        columns=["date", "dayname", "semaine", "num", "numAB", "nweek"],
    )

    planning_D = pd.DataFrame(
        generate_days(
            beg, end, settings.SKIP_DAYS_D, settings.TURN, "D"
        ),
        columns=["date", "dayname", "semaine", "num", "numAB", "nweek"],
    )

    planning_T = pd.DataFrame(
        generate_days(
            beg, end, settings.SKIP_DAYS_T, settings.TURN, "T"
        ),
        columns=["date", "dayname", "semaine", "num", "numAB", "nweek"],
    )

    return planning_C, planning_D, planning_T


def compute_slots(csv_inst_list, planning_type, empty_instructor=True, filter_uvs=None):
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
            right_on=["dayname", "semaine"],
        )

    dfm = pd.concat([df_Cm, df_Dm, df_Tm], ignore_index=True)
    return dfm


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

        func.__name__ = f"Remplace les NA dans la colonne `{colname}` par la valeur `{na_value}`"

    else:
        def fill_by_group(g):
            idx_first = g[colname].first_valid_index()
            idx_last = g[colname].last_valid_index()
            if idx_first is not None:
                if idx_first == idx_last:
                    g[colname] = g.loc[idx_first, colname]
                else:
                    logger.warning("Plusieurs valeurs non-NA dans le groupe")
                    print(g[["Nom", "Prénom", colname]])
            else:
                logger.warning("Aucune valeur non-NA dans le groupe")
            return g

        def func(df, path=None):
            check_columns(df, [colname, group_column])
            return df.groupby(group_column).apply(fill_by_group)

        func.__name__ = f"Remplace les NA dans la colonne `{colname}` en groupant par `{group_column}`"

    return func
