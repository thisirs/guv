"""
Ce module rassemble les tâches de gestion des intervenants au sein
d'une UV : fichier Excel du nombre d'heures théoriques, décompte des
heures remplacées.
"""

import os
import re

import pandas as pd
from pandas.api.types import CategoricalDtype

from ..logger import logger
from ..scripts.excel_hours import create_excel_file
from ..utils import score_codenames
from ..utils_config import Output, rel_to_dir
from .base import TaskBase, UVTask
from .utc import WeekSlots


def create_insts_list(df):
    "Agrège les données d'affectation des Cours/TD/TP"

    def course_list(e):
        "Return course list like C1, D2, T1A"
        return ', '.join(sorted(e, key=score_codenames))

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
            on="Intervenants",
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


    @classmethod
    def read_target(cls, **kwargs):
        target = cls.target_from(**kwargs)
        sts = ["MCF", "PR", "PRAG", "PRCE", "PAST", "ECC", "Doct", "ATER", "Vacataire"]
        status_type = CategoricalDtype(categories=sts, ordered=True)

        df = pd.read_excel(target, engine="openpyxl")

        df["Statut"] = df["Statut"].astype(status_type)
        df["Email"] = df["Email"].fillna("").astype("string")

        return df


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


