import os
import re

import numpy as np
import openpyxl
import pandas as pd
from PyPDF2 import PdfReader
from tabula import read_pdf
from doit.tools import config_changed
from doit.exceptions import TaskFailed
import logging

from ..config import settings
from ..exceptions import GuvUserError, ImproperlyConfigured
from ..logger import logger
from ..openpyxl_patched import fixit
from ..utils import (convert_author, convert_to_time, plural, ps, px,
                     read_dataframe, sort_values, pformat)
from ..utils_config import Output, ask_choice, generate_row, rel_to_dir, selected_uv
from .base import SemesterTask, UVTask

fixit(openpyxl)

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows

from ..openpyxl_utils import (fill_row, frame_range, get_range_cells,
                              get_row_cells)


def split_list_by_token_inclusive(lst):
    result = []
    current = []
    for item in lst:
        current.append(item)
        if item.cache:
            result.append(current)
            current = []
    if current:
        result.append(current)
    return result


class Documents:
    target_dir = "generated"
    target_name = "student_data_{step}.csv"

    def __init__(self):
        self.uv = None
        self._actions = []

    @classmethod
    def target_from(cls, **kwargs):
        target = os.path.join(
            settings.SEMESTER_DIR,
            kwargs["uv"],
            cls.target_dir,
            cls.target_name
        )
        return pformat(target, step=kwargs["step"])

    def setup(self, base_dir, uv):
        for a in self.actions:
            a.base_dir = base_dir
            a.uv = uv
        self.uv = uv

    def generate_doit_tasks(self):
        steps = split_list_by_token_inclusive(self.actions)
        for i, lst in enumerate(steps):
            step = i if i < len(steps) - 1 else "final"
            target = self.target_from(step=step, uv=self.uv)
            cache_file = self.target_from(step=i-1, uv=self.uv) if i > 0 else None

            other_deps = [d for a in lst for d in a.deps]
            deps = other_deps if cache_file is None else [cache_file] + other_deps

            def build_action(lst, cache_file, target):
                def func():
                    df = pd.read_csv(cache_file) if cache_file is not None else None
                    for a in lst:
                        logger.info(a.message())
                        try:
                            df = a.apply(df)
                        except Exception as e:
                            if settings.DEBUG <= logging.DEBUG:
                                raise e from e
                            return TaskFailed(f"L'étape `{a.name()}` a échoué : {str(e)}")

                    df.to_csv(target, index=False)
                return func

            foo = "-".join(op.hash() for op in lst)
            doit_task = {
                "basename": f"DOCS_{i}",
                "actions": [build_action(lst, cache_file, target)],
                "file_dep": deps,
                "targets": [target],
                "uptodate": [config_changed(foo)]
            }
            def format_task(doit_task):
                return "\n".join(f"{key}: {value}" for key, value in doit_task.items()
                                 if key not in ["doc"])

            logger.debug("Task properties are:")
            logger.debug(format_task(doit_task))

            yield doit_task

    def add_action(self, action):
        self._actions.append(action)

    @property
    def actions(self):
        return self._actions

    @property
    def deps(self):
        return [d for a in self.actions for d in a.deps]


class XlsStudentData(UVTask):
    """Agrège les informations spécifiées dans la variable ``DOCS``

    Agrège les informations spécifiées dans la variable ``DOCS`` du fichier
    ``config.py`` d'une UV dans un seul fichier ``effectif.xlsx``.

    """

    target_name = "effectif.xlsx"
    target_dir = "."
    unique_uv = False

    @classmethod
    def create_doit_tasks_aux(cls):
        tasks = []
        generators = []
        for planning, uv, info in selected_uv():
            instance = cls(planning, uv, info)
            task = instance.to_doit_task(
                name=f"{instance.planning}_{instance.uv}",
                uv=instance.uv
            )
            docs = instance.settings.DOCS
            if not isinstance(docs, Documents):
                raise ImproperlyConfigured("La variable DOCS doit être de type `Documents`: `DOCS = Documents()`")
            docs.setup(base_dir=os.path.join(settings.SEMESTER_DIR, uv), uv=uv)
            tasks.append(task)
            generators.append(docs.generate_doit_tasks())

        return (item for gen in [*generators, tasks] for item in gen)

    def setup(self):
        super().setup()
        if "DOCS" in self.settings:
            self.student_data = Documents.target_from(uv=self.info["uv"], step="final")
            self.file_dep = [self.student_data]
            self.target = self.build_target()
        else:
            self.file_dep = []
            self.target = None

    def get_column_dimensions(self):
        if not os.path.exists(self.target):
            return {}

        def column_dimensions(ws):
            max_column = ws.max_column
            for i in range(1, max_column+1):
                colname = ws.cell(row=1, column=i).value
                width = ws.column_dimensions[get_column_letter(i)].width
                yield colname, width

        wb = load_workbook(self.target)
        ws = wb.active
        return {colname: width for colname, width in column_dimensions(ws)}

    def run(self):
        df = pd.read_csv(self.student_data)

        # Write set of columns for completion
        fp = os.path.join(self.settings.SEMESTER_DIR, self.uv, "generated", ".columns.list")
        with open(fp, "w") as file:
            file.write("\n".join(f"{e}" for e in df.columns.values))

        # Keep dataframe ordered the same as original effectif.xlsx
        if os.path.exists(self.target):
            df_ordered = XlsStudentData.read_target(self.target)
            if len(df_ordered.index) == len(df.index):
                if "Login" in df.columns and "Login" in df_ordered.columns:
                    if set(df["Login"]) == set(df_ordered["Login"]):
                        df = df.set_index("Login", drop=False).loc[df_ordered["Login"]].reset_index(drop=True)
        else:
            df = sort_values(df, ["Nom", "Prénom"])

        # Get column dimensions of original effectif.xlsx
        column_dimensions = self.get_column_dimensions()

        wb = Workbook()
        ws = wb.active

        for r in dataframe_to_rows(df, index=False, header=True):
            ws.append(r)

        for cell in ws[1]:
            cell.style = 'Pandas'

        max_column = ws.max_column
        max_row = ws.max_row
        ws.auto_filter.ref = 'A1:{}{}'.format(
            get_column_letter(max_column),
            max_row)

        # On fige la première ligne et les deux premières colonnes
        ws.freeze_panes = "C2"

        # On redimensionne les colonnes d'après la taille précédente
        # ou la taille de l'en-tête
        for cell in ws[1]:
            width = None
            header_value = str(cell.value)

            if header_value in column_dimensions:
                width = column_dimensions[header_value]
            elif header_value == "Nom":
                width = 1.3 * 16
            elif header_value == "Prénom":
                width = 1.3 * 16
            elif header_value:
                width = 1.3 * max(len(header_value), 4)

            if width is not None:
                ws.column_dimensions[cell.column_letter].width = width

        with Output(self.target) as out:
            wb.save(out.target)

        target = os.path.splitext(self.target)[0] + ".csv"
        with Output(target) as out:
            df.to_csv(out.target, index=False)

    @staticmethod
    def read_target(student_data):
        return pd.read_excel(student_data, engine="openpyxl")


class UtcUvListToCsv(SemesterTask):
    """Crée un fichier CSV des créneaux de toutes les UVs à partir du PDF"""

    hidden = True
    target_dir = "documents"
    target_name = "UTC_UV_list.csv"

    def setup(self):
        super().setup()

        self.target = self.build_target()

        if "CRENEAU_UV" in self.settings:
            self.uv_list_filename = os.path.join(
                self.settings.SEMESTER_DIR,
                self.settings.CRENEAU_UV
            )
        else:
            self.uv_list_filename = None

        if self.uv_list_filename is not None:
            self.file_dep = [self.uv_list_filename]
        else:
            self.file_dep = []

    def read_pdf(self):
        pdf = PdfReader(open(self.uv_list_filename, 'rb'))
        npages = len(pdf.pages)

        possible_cols = ['Code enseig.', 'Activité', 'Jour', 'Heure début',
                         'Heure fin', 'Semaine', 'Locaux', 'Type créneau',
                         'Lib. créneau', 'Responsable enseig.']

        tables = []
        pdo = {"header": None}
        for i in range(npages):
            logger.info("Processing page (%d/%d)", i+1, npages)
            page = i + 1
            tabula_args = {'pages': page}
            # Use pdo.copy(): pdo is changed by read_pdf
            df = read_pdf(self.uv_list_filename, **tabula_args, pandas_options=pdo.copy())[0]

            if page == 1:
                # Detect header (might be a two-line header)
                header_height = ((re.match('[A-Z]{,3}[0-9]+', str(df.iloc[0, 0])) is None) +
                                 (re.match('[A-Z]{,3}[0-9]+', str(df.iloc[1, 0])) is None))
                if header_height == 0:
                    raise GuvUserError("No header detected")
                logger.info("Detected header has %d lines", header_height)

                # Compute single line/multiline header
                header = df.iloc[:header_height].fillna('').agg(['sum']).iloc[0]
                logger.info("Header is: %s", ' '.join(header))

                # Extract real data
                df = df.iloc[header_height:]

                # Set name of columns from header
                df = df.rename(columns=header)

                # Rename incorrectly parsed headers
                df = df.rename(columns={
                    'Activit': 'Activité',
                    'Type cr neau': 'Type créneau',
                    'Lib. cr': 'Lib. créneau',
                    'Lib.créneau': 'Lib. créneau',
                    'Lib.': 'Lib. créneau',
                    'Lib.\rcréneau': 'Lib. créneau',
                    'Heuredébut': 'Heure début',
                    'Heure d': 'Heure début',
                    'Heure déb': 'Heure début',
                    'Hteure fin': 'Heure fin',
                    'Heurefin': 'Heure fin',
                    'Locaux hybrides': "Locaux"
                })

                unknown_cols = list(set(df.columns) - set(possible_cols))
                if unknown_cols:
                    raise GuvUserError("Colonnes inconnues détectées:", ", ".join(unknown_cols))

                # Get list of detected columns
                cols = df.columns.to_list()

                # 'Semaine' is the only column that might not be
                # detected in next pages because it can be empty.
                # Store its index to insert a blank column if needed
                if "Semaine" in cols:
                    week_idx = cols.index('Semaine')
                else:
                    week_idx = cols.index('Heure fin') + 1

                logger.info("%d columns found", len(df.columns))
                logger.info(" ".join(df.columns))
            else:
                logger.info("%d columns found", len(df.columns))

                # Semaine column might be empty and not detected
                if len(df.columns) == len(cols):
                    pass
                elif len(df.columns) == len(cols) - 1:
                    df.insert(week_idx, 'Semaine', np.nan)
                else:
                    raise GuvUserError("Mauvais nombre de colonnes détectées")
                df.columns = cols

                # Detect possible multiline header
                header_height = ((re.match('[A-Z]{,3}[0-9]+', str(df.iloc[0, 0])) is None) +
                                 (re.match('[A-Z]{,3}[0-9]+', str(df.iloc[1, 0])) is None))
                logger.info("Header has %d lines", header_height)
                df = df.iloc[header_height:]

            tables.append(df)

        df = pd.concat(tables)
        useful_cols = [
            "Code enseig.",
            "Activité",
            "Jour",
            "Heure début",
            "Heure fin",
            "Semaine",
            "Locaux",
            "Lib. créneau",
        ]
        df = df[useful_cols]

        return df

    def run(self):
        if self.uv_list_filename is None:
            raise ImproperlyConfigured("La variable `CRENEAU_UV` doit être définie")

        # Lire tous les créneaux par semaine de toutes les UVs
        if not os.path.exists(self.uv_list_filename):
            uv_fn = rel_to_dir(self.uv_list_filename, self.settings.SEMESTER_DIR)
            raise FileNotFoundError(f"Le fichier n'existe pas: {uv_fn}")

        df = self.read_pdf()

        # Remove duplicate indexes from concat
        df.reset_index(drop=True, inplace=True)

        # T1 instead of T 1
        df['Lib. créneau'] = df['Lib. créneau'].replace(' +', '', regex=True)

        # A ou B au lieu de semaine A et semaine B
        df['Semaine'] = df['Semaine'].replace("^semaine ([AB])$", "\\1", regex=True)

        # Semaine ni A ni B pour les TP: demander
        uvs = self.settings.UVS

        def fix_semaineAB(group):
            if group.name[1] == 'TP' and len(group.index) > 1:
                nans = group.loc[(pd.isnull(group['Semaine']))]
                if 0 < len(nans.index) or len(nans.index) < len(group.index):
                    if group.name[0] in uvs:
                        for index, row in nans.iterrows():
                            choice = ask_choice(
                                f'Semaine pour le créneau {row["Lib. créneau"]} de TP de {group.name[0]} (A ou B) ? ',
                                choices={"A": "A", "a": "A", "B": "B", "b": "B"},
                            )
                            group.loc[index, "Semaine"] = choice
                    else:
                        group.loc[nans.index, 'Semaine'] = 'A'
                return group
            else:
                return group

        df = df.groupby(['Code enseig.', 'Activité'], group_keys=False).apply(fix_semaineAB)

        with Output(self.target) as out:
            df.to_csv(out.target, index=False)


class WeekSlotsAll(SemesterTask):
    """Rassemble les fichiers ``planning_hebdomadaire.xlsx`` de chaque UV/UE.

    Les colonnes sont :

    - Planning
    - Code enseig.
    - Jour
    - Heure début
    - Heure fin
    - Locaux
    - Semaine
    - Lib. créneau
    - Intervenants
    - Abbrev
    - Responsable

    """

    hidden = True
    target_dir = "generated"
    target_name = "planning_hebdomadaire.xlsx"

    def setup(self):
        super().setup()
        self.target = self.build_target()
        self.affectations = [
            (planning, uv, WeekSlots.target_from(**info))
            for planning, uv, info in self.selected_uv()
        ]
        self.file_dep = [f for _, _, f in self.affectations]

    def run(self):
        def func(planning, uv, xls_aff):
            df = WeekSlots.read_target(xls_aff)
            df.insert(0, "Code enseig.", uv)
            df.insert(0, "Planning", planning)
            return df

        df_affs = [func(planning, uv, xls_aff) for planning, uv, xls_aff in self.affectations]
        df_aff = pd.concat(df_affs, ignore_index=True)
        df_aff.Semaine = df_aff.Semaine.astype(object)

        with Output(self.target) as out:
            df_aff.to_excel(out.target, index=False)

    @staticmethod
    def read_target(week_slots_all):
        df = pd.read_excel(week_slots_all, engine="openpyxl")

        df["Heure début"] = df["Heure début"].apply(convert_to_time)
        df["Heure fin"] = df["Heure fin"].apply(convert_to_time)

        return df


class PlanningSlotsAll(SemesterTask):
    """Rassemble les fichiers `plannings.xlsx` de chaque UE/UV."""

    hidden = True
    unique_uv = False
    target_dir = "generated"
    target_name = "planning_all.xlsx"

    def setup(self):
        super().setup()
        self.target = self.build_target()
        self.planning_slots_files = [
            (planning, uv, PlanningSlots.target_from(**info))
            for planning, uv, info in self.selected_uv()
        ]
        self.file_dep = [f for _, _, f in self.planning_slots_files]

    def run(self):
        def func(planning, uv, xls_aff):
            df = PlanningSlots.read_target(xls_aff)
            df.insert(0, "Code enseig.", uv)
            df.insert(0, "Planning", planning)
            return df

        dfs = [
            func(planning, uv, xls_aff)
            for planning, uv, xls_aff in self.planning_slots_files
        ]

        df = pd.concat(dfs, ignore_index=True)
        df.Semaine = df.Semaine.astype(object)

        with Output(self.target) as out:
            df.to_excel(out.target, index=False)

    @staticmethod
    def read_target(planning_slots_all):
        df = pd.read_excel(planning_slots_all, engine="openpyxl")

        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["Heure début"] = df["Heure début"].apply(convert_to_time)
        df["Heure fin"] = df["Heure fin"].apply(convert_to_time)

        return df


class Planning(SemesterTask):
    """Fichier csv de tous les jours composant le ou les plannings du semestre."""

    hidden = True
    target_name = "planning_{planning}.csv"
    target_dir = "generated"

    def setup(self):
        super().setup()
        self.target = self.build_target()

        self.targets = [
            self.build_target(planning=planning)
            for planning in self.settings.PLANNINGS
        ]

        # Set uptodate value without raising Exception or displaying warnings
        self.uptodate = {"plannings": ", ".join(self.settings.PLANNINGS)}
        for planning in self.settings.PLANNINGS:
            props = self.settings.PLANNINGS[planning]

            for name in ["PL_BEG", "PL_END", "TURN", "SKIP_DAYS_C", "SKIP_DAYS_D", "SKIP_DAYS_T"]:
                try:
                    if name in props:
                        value = props[name]
                    else:
                        value = self.settings[name]
                    self.uptodate[planning + "_" + name.lower()] = value
                except ImproperlyConfigured:
                    self.uptodate[planning + "_" + name.lower()] = None

    def run(self):
        for planning in self.settings.PLANNINGS:
            props = self.settings.PLANNINGS[planning]

            for name in ["PL_BEG", "PL_END", "TURN", "SKIP_DAYS_C", "SKIP_DAYS_D", "SKIP_DAYS_T"]:
                if name not in props:
                    logger.info(
                        f"La clé `{name}` est absente du planning `{planning}` dans la "
                        f"variable `PLANNINGS`, utilisation de la variable globale `{name}`."
                    )
                    props[name] = self.settings[name]

            pl_beg = props["PL_BEG"]
            pl_end = props["PL_END"]
            skip_days_c = props["SKIP_DAYS_C"]
            skip_days_d = props["SKIP_DAYS_D"]
            skip_days_t = props["SKIP_DAYS_T"]
            turn = props["TURN"]

            for d in skip_days_c:
                if d < pl_beg or d > pl_end:
                    logger.warning("Le jour %s renseigné dans `SKIP_DAYS_C` ne fait pas partie du planning", d)

            for d in skip_days_d:
                if d < pl_beg or d > pl_end:
                    logger.warning("Le jour %s renseigné dans `SKIP_DAYS_D` ne fait pas partie du planning", d)

            for d in skip_days_t:
                if d < pl_beg or d > pl_end:
                    logger.warning("Le jour %s renseigné dans `SKIP_DAYS_T` ne fait pas partie du planning", d)

            for d in turn:
                if d < pl_beg or d > pl_end:
                    logger.warning("Le jour %s renseigné dans `TURN` ne fait pas partie du planning", d)

            # DataFrame of days in planning
            planning_C = pd.DataFrame(
                generate_row(pl_beg, pl_end, skip_days_c, turn),
                columns=["date", "Jour", "num", "Semaine", "numAB", "nweek"],
            )
            planning_D = pd.DataFrame(
                generate_row(pl_beg, pl_end, skip_days_d, turn),
                columns=["date", "Jour", "num", "Semaine", "numAB", "nweek"],
            )
            planning_T = pd.DataFrame(
                generate_row(pl_beg, pl_end, skip_days_t, turn),
                columns=["date", "Jour", "num", "Semaine", "numAB", "nweek"],
            )

            for plng, text, number in (
                    (planning_C, "cours", 14),
                    (planning_D, "TD", 13),
                    (planning_T, "TP", 14),
            ):
                counts = plng["Jour"].value_counts()
                unique = counts.unique()
                if len(unique) != 1:
                    serie = ", ".join(f"{index} : {value}" for index, value in counts.items())
                    logger.warning("Le nombre de semaines de %s n'est pas le même pour tous les jours : %s", text, serie)
                elif unique.item() != number:
                    logger.warning("Le nombre de semaines de %s est différent de %d : %d", text, number, unique.item())

            planning_C["Activité"] = "Cours"
            planning_D["Activité"] = "TD"
            planning_T["Activité"] = "TP"
            df = pd.concat((planning_C, planning_D, planning_T))

            with Output(self.target.format(planning=planning)) as out:
                df.to_csv(out.target, index=False)


class PlanningSlots(UVTask):
    """Fichier Excel des créneaux sur le planning entier.

    Les colonnes du fichier sont :

    - Code enseig.: SY02
    - Activité: TP
    - Jour: Lundi
    - Heure début: 14:15
    - Heure fin: 16:15
    - Semaine: B
    - Locaux: BF B 113
    - Lib. créneau: T1
    - Planning: P2021
    - Responsable:
    - Intervenants: Fisher
    - Responsable:
    - date: 2021-03-08
    - num: 1
    - numAB: 1
    - nweek: 4

"""

    hidden = True
    unique_uv = False
    target_name = "planning.xlsx"
    target_dir = "generated"

    def setup(self):
        super().setup()
        self.target = self.build_target()

        self.week_slots = WeekSlots.target_from(**self.info)
        self.planning = Planning.target_from(**self.info)
        self.file_dep = [self.week_slots, self.planning]

    def run(self):
        # Load all days in the planning with "Activité" being either "Cours",
        # "TD", "TP"
        planning = pd.read_csv(self.planning)

        # Load week slots and rename "Activité" column that need not be "Cours",
        # "TD", "TP" only.
        df = WeekSlots.read_target(self.week_slots)
        df = df.rename(columns={"Activité": "Activité alt"})
        mask_C = df["Activité alt"] == "Cours"
        mask_D = df["Activité alt"] == "TD"
        mask_T = df["Activité alt"] == "TP"

        # Separate based on "Activité alt"
        df_C = df.loc[mask_C]
        df_D = df.loc[mask_D]
        df_T = df.loc[mask_T]

        # Handle where "Activité alt" is not "Cours", "TD" or "TP" in week slots
        df_other = df.loc[~(mask_C | mask_D | mask_T)]
        if len(df_other) > 0:
            for name, group in df_other.groupby("Activité alt"):
                logger.warning(
                    "%d créneau%s %s étiqueté%s `%s`, le%s compter comme `Cours`, `TD` ou `TP` ?",
                    len(df_other),
                    px(len(df_other)),
                    plural(len(df_other), "sont", "est"),
                    ps(len(df_other)),
                    name,
                    ps(len(df_other)),
                )
                result = ask_choice("Choix ? ", {"Cours": "Cours", "TD": "TD", "TP": "TP"})
                if result == "Cours":
                    df_C = pd.concat((df_C, df_other))
                elif result == "TD":
                    df_D = pd.concat((df_D, df_other))
                elif result == "TP":
                    df_T = pd.concat((df_T, df_other))
                else:
                    raise RuntimeError("Logical error")

        planning_noweek = planning.drop("Semaine", axis=1)

        planning_noweek_Cours = planning_noweek.loc[planning_noweek["Activité"] == "Cours"]
        df_Cp = pd.merge(df_C, planning_noweek_Cours, how="left", on="Jour")

        planning_noweek_TD = planning_noweek.loc[planning_noweek["Activité"] == "TD"]
        df_Dp = pd.merge(df_D, planning_noweek_TD, how="left", on="Jour")

        if df_T["Semaine"].hasnans:
            planning_noweek_TP = planning_noweek.loc[planning_noweek["Activité"] == "TP"]
            df_Tp = pd.merge(df_T, planning_noweek_TP, how="left", on="Jour")
        else:
            planning_TP = planning.loc[planning_noweek["Activité"] == "TP"]
            df_Tp = pd.merge(df_T, planning_TP, how="left", on=["Jour", "Semaine"])

        dfp = pd.concat([df_Cp, df_Dp, df_Tp], ignore_index=True)

        with Output(self.target) as out:
            dfp.to_excel(out.target, index=False)

    @staticmethod
    def read_target(planning_slots):
        df = pd.read_excel(planning_slots, engine="openpyxl")

        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["Heure début"] = df["Heure début"].apply(convert_to_time)
        df["Heure fin"] = df["Heure fin"].apply(convert_to_time)

        return df


class WeekSlots(UVTask):
    """Fichier Excel des créneaux hebdomadaires d'une UV.

    Crée un fichier "planning_hebdomadaire.xlsx" dans chaque dossier
    d'UV/UE. Le fichier est prérempli d'après le fichier pdf des
    créneaux de toutes les UVs. Si l'UV/UE n'est pas trouvée, un
    fichier avec en-tête mais sans créneau est créé.

    """

    hidden = True
    unique_uv = False
    target_name = "planning_hebdomadaire.xlsx"
    target_dir = "documents"

    def setup(self):
        super().setup()
        self.target = self.build_target()
        self.uvlist_csv = UtcUvListToCsv.target_from()
        self.file_dep = [self.uvlist_csv]

    def run(self):
        df = pd.read_csv(self.uvlist_csv)
        self.df_uv = df.loc[df["Code enseig."] == self.uv, :]

        output_obj = self.create_excel_file()
        if output_obj.action not in ["abort", "keep"]:
            workbook = load_workbook(filename=self.target)
            self.add_second_worksheet(workbook)

    @staticmethod
    def read_target(week_slots):
        df = pd.read_excel(week_slots, engine="openpyxl", dtype={
            "Activité": str,
            "Jour": str,
            "Heure début": str,
            "Heure fin": str,
            "Semaine": str,
            "Locaux": str,
            "Lib. créneau": str,
            "Intervenants": str,
            "Abbrev": str,
            "Responsable": str
        })
        if len(df.index) == 0:
            fn = rel_to_dir(week_slots)
            logger.warning(f"Le fichier `{fn}` est vide")

        if df["Activité"].isnull().any():
            fn = rel_to_dir(week_slots)
            raise GuvUserError(f"La colonne `Activité` du fichier `{fn}` ne doit pas contenir d'élément vide.")

        rest = set(df["Activité"]) - set(["Cours", "TD", "TP"])
        if rest:
            rest_msg = ", ".join(f"`{e}`" for e in rest)
            fn = rel_to_dir(week_slots)
            logger.warning("La colonne `Activité` du fichier `%s` contient des libellés non standards (`Cours`, `TD` et `TP`) : %s", fn, rest_msg)

        if df["Jour"].isnull().any():
            fn = rel_to_dir(week_slots)
            raise GuvUserError(f"La colonne `Jour` du fichier `{fn}` ne doit pas contenir d'élément vide.")

        rest = set(df["Jour"]) - set(["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"])
        if rest:
            rest_msg = ", ".join(f"`{e}`" for e in rest)
            fn = rel_to_dir(week_slots)
            raise GuvUserError(f"La colonne `Jour` du fichier `{fn}` ne doit contenir que des jours de la semaine, elle contient {rest_msg}")

        if df["Lib. créneau"].isnull().any():
            fn = rel_to_dir(week_slots)
            raise GuvUserError(f"La colonne `Lib. créneau` du fichier `{fn}` ne doit pas contenir d'élément vide.")

        df["Heure début"] = df["Heure début"].apply(convert_to_time)
        df["Heure fin"] = df["Heure fin"].apply(convert_to_time)

        # Populate "Abbrev" column where possible
        empty = df["Abbrev"].isna() & ~df["Intervenants"].isna()
        df.loc[empty, "Abbrev"] = df.loc[empty, "Intervenants"].apply(convert_author)

        # Warn if abbrev clashes
        for index, group in df.groupby("Abbrev"):
            insts = group["Intervenants"].dropna().unique()
            if len(insts) > 1:
                insts_list = ", ".join(insts)
                fn = rel_to_dir(week_slots)
                logger.warning(f"Les intervenants suivants ont les mêmes initiales : {insts_list}. "
                               f"Modifier la colonne `Abbrev` dans le fichier `{fn}`.")

        return df

    def create_excel_file(self):
        df = pd.read_csv(self.uvlist_csv)
        self.df_uv = df.loc[df["Code enseig."] == self.uv, :]

        # Test if UV/UE is in listing from UtcUvListToCsv
        if len(self.df_uv) == 0:
            creneau_uv = rel_to_dir(self.settings.CRENEAU_UV)
            logger.warning(
                "L'UV/UE `%s` n'existe pas dans le fichier `%s`, "
                "un fichier Excel sans créneau est créé.",
                self.uv,
                creneau_uv
            )
            columns = [
                "Activité",
                "Jour",
                "Heure début",
                "Heure fin",
                "Locaux",
                "Semaine",
                "Lib. créneau",
                "Intervenants",
                "Abbrev",
                "Responsable",
            ]
            self.df_uv = pd.DataFrame(columns=columns)
        else:
            self.df_uv = self.df_uv.sort_values(["Lib. créneau", "Semaine"])
            self.df_uv = self.df_uv.drop(["Code enseig."], axis=1)
            self.df_uv["Intervenants"] = np.nan
            self.df_uv["Abbrev"] = np.nan
            self.df_uv["Responsable"] = np.nan

        # Write to disk
        with Output(self.target, protected=True) as out:
            self.df_uv.to_excel(out.target, sheet_name="Intervenants", index=False)

        # Return decision in Output
        return out

    def add_second_worksheet(self, workbook):
        worksheet = workbook.create_sheet("Décompte des heures")

        # Make current worksheet the default one, useful for get_address_of_cell
        workbook.active = worksheet

        ref = worksheet.cell(1, 1)
        num_record = len(self.df_uv)
        if num_record == 0:
            num_record = 10

        semAB = not self.df_uv.loc[self.df_uv["Activité"] == "TP", "Semaine"].isna().all()
        has_TP = "TP" in self.df_uv["Activité"].values

        keywords = [
            "Intervenants",
            "Statut",
            "Cours",
            "TD",
            "TP",
            "Heures Cours prév",
            "Heures TD prév",
            "Heures TP prév",
            "UTP",
            "Heure équivalent TD",
            "Heure brute"
        ]

        if not has_TP:
            del keywords[keywords.index("Statut")]
            del keywords[keywords.index("TP")]
            del keywords[keywords.index("Heures TP prév")]

        # Write header
        row_cells = get_row_cells(ref, 0, *keywords)
        headers = {e: e for e in keywords}
        if has_TP and semAB:
            headers["TP"] = "TP A/B"
        fill_row(row_cells, **headers)
        for cell in row_cells.values():
            cell.style = "Pandas"

        # Write rows
        for i in range(num_record):
            row_cells = get_row_cells(ref, i+1, *keywords)
            elts = {
                "Heures Cours prév": lambda row: "=2*16*{}".format(row["Cours"].coordinate),
                "Heures TD prév": lambda row: "=2*16*{}".format(row["TD"].coordinate),
                "Heure équivalent TD": lambda row: "=2/3*{}".format(row["UTP"].coordinate),
            }

            if has_TP:
                elts["Heures TP prév"] = lambda row: "=2*{num_week}*{TP_cell}".format(
                    TP_cell=row["TP"].coordinate,
                    num_week="8" if semAB else "16"
                )
                elts["UTP"] = lambda row: "=2*16*2.25*{cours_cell}+2*16*1.5*{TD_cell}+2*{num_week}*{TP_cell}*{status_cell}".format(
                    cours_cell=row["Cours"].coordinate,
                    TD_cell=row["TD"].coordinate,
                    TP_cell=row["TP"].coordinate,
                    status_cell=row["Statut"].coordinate,
                    num_week="8" if semAB else "16"
                )
                elts["Heure brute"] = lambda row: "=2*16*{cours_cell}+2*16*{TD_cell}+2*{num_week}*{TP_cell}".format(
                    cours_cell=row["Cours"].coordinate,
                    TD_cell=row["TD"].coordinate,
                    TP_cell=row["TP"].coordinate,
                    num_week="8" if semAB else "16"
                )
                elts["Statut"] = 1.5
            else:
                elts["UTP"] = lambda row: "=2*16*2.25*{cours_cell}+2*16*1.5*{TD_cell}".format(
                    cours_cell=row["Cours"].coordinate,
                    TD_cell=row["TD"].coordinate,
                )
                elts["Heure brute"] = lambda row: "=2*16*{cours_cell}+2*16*{TD_cell}".format(
                    cours_cell=row["Cours"].coordinate,
                    TD_cell=row["TD"].coordinate,
                )

            fill_row(row_cells, **elts)

        frame_range(ref, row_cells[keywords[-1]])

        # Write real
        row_cells = get_row_cells(ref, num_record+1, *keywords)
        range_cells = get_range_cells(ref.below(), num_record-1, *keywords)
        row_cells["Cours"].value = "=SUM({})".format(range_cells["Cours"])
        row_cells["TD"].value = "=SUM({})".format(range_cells["TD"])
        if has_TP:
            row_cells["TP"].value = "=SUM({})".format(range_cells["TP"])
        row_cells["Cours"].left().text("Total")

        # Write expected
        n_cours = len(self.df_uv.loc[self.df_uv["Activité"] == "Cours"])
        n_TD = len(self.df_uv.loc[self.df_uv["Activité"] == "TD"])

        row_cells = get_row_cells(ref, num_record+2, *keywords)
        row_cells["Cours"].value = n_cours
        row_cells["TD"].value = n_TD
        if has_TP:
            n_TP = len(self.df_uv.loc[self.df_uv["Activité"] == "TP"])
            row_cells["TP"].value = n_TP
        row_cells["Cours"].left().text("Attendu")

        workbook.save(self.target)
