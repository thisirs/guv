import os
import time
from datetime import timedelta
import pandas as pd

from .utils import rel_to_dir
from .config import semester_settings


class NotUVDirectory(Exception):
    pass


def selected_uv(all="dummy"):
    "Génère les UV configurées dans le fichier config.py du semestre"

    if semester_settings.UV_DIR is not None:
        yield get_unique_uv()

    else:
        uv_to_planning = {
            uv: plng
            for plng, props in semester_settings.PLANNINGS.items()
            for uv in props["UVS"]
        }

        if not set(semester_settings.UVS).issubset(set(uv_to_planning.keys())):
            raise ValueError("Des UVS n'ont pas de planning associé")

        for uv in semester_settings.UVS:
            plng = uv_to_planning[uv]
            info = {
                "uv": uv,
                "planning": plng
            }
            yield plng, uv, info


# def selected_uv(all=False):
#     "Génère les UV configurées dans le fichier config.py du semestre"

#     if all:
#         for planning, settings0 in semester_settings.PLANNINGS.items():
#             uvp = settings0['UVS']
#             for uv in uvp:
#                 yield planning, uv, {'planning': planning, 'uv': uv}
#     else:
#         for planning, settings0 in semester_settings.PLANNINGS.items():
#             uvp = settings0['UVS']
#             for uv in set(semester_settings.SELECTED_UVS).intersection(set(uvp)):
#                 info = {'planning': planning, 'uv': uv}
#                 info["path"]
#                 yield planning, uv, {'planning': planning, 'uv': uv}

def get_unique_uv():
    if semester_settings.UV_DIR is not None:
        uv = semester_settings.UV_DIR
        if uv not in semester_settings.UVS:
            raise Exception("L'UV n'est pas enregistrée")

        plngs = [
            plng
            for plng, props in semester_settings.PLANNINGS.items()
            if uv in props["UVS"]
        ]

        if not plngs:
            raise Exception("L'UV ne fait partie d'aucun planning")

        if len(plngs) >= 2:
            raise Exception("L'UV fait partie de plusieurs plannings")

        plng = plngs[0]
        info = {"uv": uv, "planning": plng}
        return plng, uv, info
    else:
        raise NotUVDirectory


# def get_unique_uv():
#     uvs = list(selected_uv())
#     if len(uvs) != 1:
#         uvs = [uv for _, uv, _ in uvs]
#         raise Exception(f"Une seule UV doit être sélectionnée. Les UVs sélectionnées sont: {', '.join(uvs)}")
#     return uvs[0]


def documents(fn, **info):
    if "local" in info:
        base_dir = os.path.basename(semester_settings.SEMESTER_DIR)
    else:
        base_dir = semester_settings.SEMESTER_DIR

    if 'uv' in info or 'ue' in info:
        uv = info.get('uv', info.get('ue'))
        return os.path.join(base_dir, uv, 'documents', fn)
    else:
        return os.path.join(base_dir, 'documents', fn)


def generated(fn, **info):
    if "local" in info:
        base_dir = ""
    else:
        base_dir = semester_settings.SEMESTER_DIR

    if 'uv' in info or 'ue' in info:
        uv = info.get('uv', info.get('ue'))
        return os.path.join(base_dir, uv, 'generated', fn)
    else:
        return os.path.join(base_dir, 'generated', fn)


class Output():
    def __init__(self, target, protected=False):
        self.target = target
        self.protected = protected

    def __enter__(self):
        if os.path.exists(self.target):
            if self.protected:
                while True:
                    try:
                        choice = input('Le fichier `%s'' existe déjà. Écraser (d), garder (g), sauvegarder (s), annuler (a) ? ' % rel_to_dir(self.target, semester_settings.SEMESTER_DIR))
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
                      rel_to_dir(self.target, semester_settings.SEMESTER_DIR))
        else:
            dirname = os.path.dirname(self.target)
            if not os.path.exists(dirname):
                os.makedirs(dirname)

        return lambda: self.target

    def __exit__(self, type, value, traceback):
        if type is ZeroDivisionError:
            return True
        if type is None:
            print(f"Wrote `{rel_to_dir(self.target, semester_settings.SEMESTER_DIR)}'")


def create_plannings(planning_type):
    """Generate list of working days according to planning"""

    def generate_days(beg, end, skip, turn, course):
        """Generate working days from BEG to END"""

        daynames = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
        delta = end - beg
        semaine = {"Lundi": 0, "Mardi": 0, "Mercredi": 0, "Jeudi": 0, "Vendredi": 0}

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

    beg = semester_settings.PLANNINGS[planning_type]["PL_BEG"]
    end = semester_settings.PLANNINGS[planning_type]["PL_END"]

    planning_C = pd.DataFrame(
        generate_days(
            beg, end, semester_settings.SKIP_DAYS_C, semester_settings.TURN, "C"
        ),
        columns=["date", "dayname", "semaine", "num", "numAB", "nweek"],
    )

    planning_D = pd.DataFrame(
        generate_days(
            beg, end, semester_settings.SKIP_DAYS_D, semester_settings.TURN, "D"
        ),
        columns=["date", "dayname", "semaine", "num", "numAB", "nweek"],
    )

    planning_T = pd.DataFrame(
        generate_days(
            beg, end, semester_settings.SKIP_DAYS_T, semester_settings.TURN, "T"
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
