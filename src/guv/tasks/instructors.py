"""
Ce module rassemble les tâches de gestion des intervenants au sein
d'une UV : fichier Excel du nombre d'heures théoriques, décompte des
heures remplacées.
"""

import os

import pandas as pd
from pandas.api.types import CategoricalDtype

from ..logger import logger
from ..scripts.excel_hours import create_excel_file
from ..utils_config import Output, rel_to_dir
from .base import TaskBase, UVTask
from .utc import WeekSlots


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


class WeekSlotsDetails(UVTask):
    """Fichier Excel des intervenants par UV avec détails.

    Les détails sont pris dans le fichier de détails global. Les
    affectations sont prises pour chaque UV.
    """

    hidden = True
    target_dir = "generated"
    target_name = "intervenants_details.xlsx"

    def setup(self):
        super().setup()
        self.target = self.build_target()

        self.insts = XlsInstructors.target_from()
        self.inst_uv = WeekSlots.target_from(**self.info)
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
        self.target = self.build_target()

        self.week_slots_details = WeekSlotsDetails.target_from(**self.info)
        self.file_dep = [self.week_slots_details]

    def run(self):
        df = WeekSlotsDetails.read_target(**self.info)

        dfs = df.sort_values(
            ["Responsable", "Statut"], ascending=False
        )
        dfs = dfs.reset_index()

        with Output(self.target, protected=True) as out:
            create_excel_file(out.target, dfs)


