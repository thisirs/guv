"""
Ce module rassemble les tâches de gestion des intervenants au sein
d'une UV : fichier Excel du nombre d'heures théoriques, décompte des
heures remplacées.
"""

import os
import re

import openpyxl
import pandas as pd
from pandas.api.types import CategoricalDtype

from ..logger import logger
from ..openpyxl_patched import fixit
from ..scripts.excel_hours import create_excel_file
from ..utils import lib_list
from ..utils_config import Output, selected_uv, rel_to_dir
from .base import TaskBase, UVTask
from .utc import UtcUvListToCsv

fixit(openpyxl)

from ..openpyxl_utils import fill_row, get_range_from_cells


def create_insts_list(df):
    "Agrège les données d'affectation des Cours/TD/TP"

    def course_list(e):
        "Return course list like C1, D2, T1A"
        return ', '.join(sorted(e, key=lib_list))

    def score(libs):
        "Renvoie un tuple comptant les types de cours Cours/TD/TP"
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

    def myapply(df):
        e = df['Lib. créneau'] + df['Semaine'].fillna('')
        resp = int(df['Responsable'].sum())
        s = score(e)
        return pd.Series({
            'CourseList': course_list(e),
            'SortCourseList': s,
            'Cours': s[0],
            'TD': s[1],
            'TP': s[2],
            'Responsable': resp
        })

    df = df.groupby('Intervenants')
    df = df.apply(myapply)
    df = df.reset_index()

    return(df)


class XlsInstructors(TaskBase):
    """Fichier de détails global des intervenants toutes UV confondues.

    Il sert à la tâche :class:`~guv.tasks.moodle.HtmlInst` pour
    générer un descriptif des intervenants d'une UV et à la tâche
    :class:`guv.tasks.instructors.XlsUTP` pour le calcul des UTP
    effectuées et des remplacements.

    """

    hidden = True
    target_dir = "documents"
    target_name = "intervenants.xlsx"

    def setup(self):
        super().setup()
        self.target = self.build_target()

    def run(self):
        if not os.path.exists(self.target):
            logger.info(
                "Le fichier `%s` n'existe pas, création d'un fichier vide",
                rel_to_dir(self.target, self.settings.SEMESTER_DIR),
            )
            columns = ["Intervenants", "Statut", "Email", "Website"]
            with Output(self.target) as out:
                pd.DataFrame(columns=columns).to_excel(out.target, index=False)


class WeekSlotsAll(TaskBase):
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
            for planning, uv, info in selected_uv()
        ]
        self.file_dep = [f for _, _, f in self.affectations]

    def run(self):
        def func(planning, uv, xls_aff):
            df = pd.read_excel(xls_aff, engine="openpyxl")
            df.insert(0, "Code enseig.", uv)
            df.insert(0, "Planning", planning)
            return df

        df_affs = [func(planning, uv, xls_aff) for planning, uv, xls_aff in self.affectations]
        df_aff = pd.concat(df_affs, ignore_index=True)
        df_aff.Semaine = df_aff.Semaine.astype(object)

        with Output(self.target) as out:
            df_aff.to_excel(out.target, index=False)


def read_xls_details(fn):
    """Lit un fichier Excel avec un ordre sur la colonne 'Statut'."""

    sts = ["MCF", "PR", "PRAG", "PRCE", "PAST", "ECC", "Doct", "ATER", "Vacataire"]
    status_type = CategoricalDtype(categories=sts, ordered=True)

    return pd.read_excel(fn, engine="openpyxl", dtype={
        'Statut': status_type
    })


class XlsInstDetails(UVTask):
    """Fichier Excel des intervenants par UV avec détails

    Les détails sont pris dans le fichier de détails global. Les
    affectations sont prises pour chaque UV.
    """

    hidden = True
    target_dir = "generated"
    target_name = "intervenants_details.xlsx"

    def setup(self):
        super().setup()
        self.insts = XlsInstructors.target_from()
        self.inst_uv = WeekSlots.target_from(**self.info)
        self.target = self.build_target()
        self.file_dep = [self.inst_uv, self.insts]

    def run(self):
        inst_uv = pd.read_excel(self.inst_uv, engine="openpyxl")
        insts = pd.read_excel(self.insts, engine="openpyxl")

        # Add details from inst_details
        df_outer = inst_uv.merge(
            insts,
            how="outer",
            left_on="Intervenants",
            right_on="Intervenants",
            indicator=True,
        )

        df_left = df_outer[df_outer["_merge"].isin(["left_only", "both"])]
        df_left = df_left.drop(["_merge"], axis=1)

        df_missing = df_outer[df_outer["_merge"].isin(["left_only"])]
        inst_missing = df_missing["Intervenants"].unique()
        for inst in inst_missing:
            logger.warning("Pas d'informations détaillées sur l'intervenant: %s", inst)

        with Output(self.target) as out:
            df_left.to_excel(out.target, index=False)


class XlsUTP(UVTask):
    """Crée un document Excel pour calcul des heures et remplacements."""

    target_dir = "generated"
    target_name = "remplacement.xlsx"

    def setup(self):
        super().setup()
        self.xls = WeekSlots.target_from(**self.info)
        self.insts = XlsInstructors.target_from()
        self.target = self.build_target()
        self.file_dep = [self.xls, self.insts]

    def run(self):
        df = pd.read_excel(self.xls, engine="openpyxl")

        # Add details
        df_details = read_xls_details(self.insts)

        if df["Intervenants"].isnull().all():
            raise Exception(
                "Pas d'intervenants renseignés dans le fichier %s" % self.xls
            )
        else:
            df_insts = create_insts_list(df)

        # Add details from df_details
        df = df_insts.merge(
            df_details, how="left", left_on="Intervenants", right_on="Intervenants"
        )

        dfs = df.sort_values(
            ["Responsable", "Statut", "SortCourseList"], ascending=False
        )
        dfs = dfs.reset_index()

        with Output(self.target, protected=True) as out:
            create_excel_file(out.target, dfs)


class WeekSlots(UVTask):
    """Fichier Excel des créneaux de toutes les UV configurées.

    Crée un fichier "planning_hebdomadaire.xlsx" dans chaque dossier
    d'UV/UE. Le fichier est prérempli d'après le fichier pdf des
    créneaux de toutes les UVs. Si l'UV/UE n'est pas trouvée, un
    fichier avec en-tête mais sans créneau est créé.

    """

    unique_uv = False
    target_name = "planning_hebdomadaire.xlsx"
    target_dir = "documents"

    def setup(self):
        super().setup()
        self.uvlist_csv = UtcUvListToCsv.target_from()
        self.target = self.build_target()
        self.file_dep = [self.uvlist_csv]

    def run(self):
        output_obj = self.create_excel_file()
        if output_obj.action != "abort":
            self.add_second_worksheet()

    def create_excel_file(self):
        df = pd.read_csv(self.uvlist_csv)
        self.df_uv = df.loc[df["Code enseig."] == self.uv, :]

        # Test if UV/UE is in listing from UtcUvListToCsv
        if len(self.df_uv) == 0:
            creneau_uv = rel_to_dir(self.settings.CRENEAU_UV, self.settings.CWD)
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
                "Responsable",
            ]
            df_uv_select = pd.DataFrame(columns=columns)
        else:
            df_uv_select = self.df_uv.sort_values(["Lib. créneau", "Semaine"])
            df_uv_select = df_uv_select.drop(["Code enseig."], axis=1)
            df_uv_select["Intervenants"] = ""
            df_uv_select["Responsable"] = ""

        # Write to disk
        with Output(self.target, protected=True) as out:
            df_uv_select.to_excel(out.target, sheet_name="Intervenants", index=False)

        # Return decision in Output
        return out

    def add_second_worksheet(self):
        N = 10
        workbook = openpyxl.load_workbook(self.target)
        worksheet = workbook.create_sheet("Décompte des heures")

        ref_cell = worksheet.cell(2, 2)

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

        fill_row(ref_cell, *keywords)

        def get_cell_in_row(ref_cell, *keywords):
            def func(cell, keyword):
                if keyword in keywords:
                    return cell.parent.cell(
                        row=cell.row,
                        column=ref_cell.col_idx + keywords.index(keyword)
                    )
                else:
                    raise Exception

            return func

        cell_in_row = get_cell_in_row(ref_cell, *keywords)

        for i in range(N):
            cell = ref_cell.below(i + 1)
            elts = [
                None,
                None,
                None,
                None,
                None,
                lambda cell: "=2*16*{}".format(cell_in_row(cell, "Cours").coordinate),
                lambda cell: "=2*16*{}".format(cell_in_row(cell, "TD").coordinate),
                lambda cell: "=2*16*{}".format(cell_in_row(cell, "TP").coordinate),
                lambda cell: "=2*16*2.25*{}+2*16*1.5*{}+2*16*{}*{}".format(
                    cell_in_row(cell, "Cours").coordinate,
                    cell_in_row(cell, "TD").coordinate,
                    cell_in_row(cell, "TP").coordinate,
                    cell_in_row(cell, "Statut").coordinate,
                ),
                lambda cell: "=2/3*{}".format(
                    cell_in_row(cell, "UTP").coordinate,
                ),
                lambda cell: "=2*16*{}+2*16*{}+2*16*{}".format(
                    cell_in_row(cell, "Cours").coordinate,
                    cell_in_row(cell, "TD").coordinate,
                    cell_in_row(cell, "TP").coordinate,
                )
            ]
            fill_row(cell, *elts)

        total_cell = ref_cell.below(N+1)
        expected_cell = ref_cell.below(N+2)

        n_cours = len(self.df_uv.loc[self.df_uv["Activité"] == "Cours"])
        n_TD = len(self.df_uv.loc[self.df_uv["Activité"] == "TD"])
        n_TP = len(self.df_uv.loc[self.df_uv["Activité"] == "TP"])

        first_cours = ref_cell.below().right(2)
        first_TD = ref_cell.below().right(3)
        first_TP = ref_cell.below().right(4)

        last_cours = ref_cell.below(N).right(2)
        last_TD = ref_cell.below(N).right(3)
        last_TP = ref_cell.below(N).right(4)

        range_ = get_range_from_cells(first_cours, last_cours)
        total_cell.right(2).text(f"=SUM({range_})")

        range_ = get_range_from_cells(first_TD, last_TD)
        total_cell.right(3).text(f"=SUM({range_})")

        range_ = get_range_from_cells(first_TP, last_TP)
        total_cell.right(4).text(f"=SUM({range_})")

        expected_cell.right().text(n_cours)
        expected_cell.right(2).text(n_TD)
        expected_cell.right(3).text(n_TP)

        workbook.save(self.target)
