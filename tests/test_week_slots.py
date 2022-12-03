import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_utc_uv_list_to_csv", name="test_week_slots")
class TestWeekSlots:

    def test_week_slots(self, guv, xlsx):
        uv = guv.uvs[0]
        guv.cd(guv.semester)
        guv().succeed()
        assert (guv.cwd / uv / "documents" / "planning_hebdomadaire.xlsx").is_file()

        doc = xlsx.tabular(
            guv.cwd / uv / "documents" / "planning_hebdomadaire.xlsx",
            sheet_name="Intervenants",
        )
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


