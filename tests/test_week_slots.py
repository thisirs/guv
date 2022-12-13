import pytest
from tests.plugins.test_path import path_dependency

import pandas as pd


@path_dependency("test_utc_uv_list_to_csv", name="test_week_slots")
class TestWeekSlots:

    def test_week_slots(self, guv, xlsx):
        guv.cd(guv.semester)
        guv().succeed()

        for uv in guv.uvs:
            assert (guv.cwd / uv / "documents" / "planning_hebdomadaire.xlsx").is_file()

            with xlsx.tabular(
                guv.cwd / uv / "documents" / "planning_hebdomadaire.xlsx",
                sheet_name="Intervenants",
            ) as doc:
                doc.check_columns(
                    "Activité",
                    "Jour",
                    "Heure début",
                    "Heure fin",
                    "Semaine",
                    "Locaux",
                    "Lib. créneau",
                    "Intervenants",
                    "Abbrev",
                    "Responsable",
                )

                insts = [f"Inst {uv} {i}" for i in range(len(doc.df))]

                doc.df["Intervenants"] = pd.Series(insts)
