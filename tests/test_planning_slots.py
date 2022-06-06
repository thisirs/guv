import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_week_slots", name="test_planning_slots")
class TestPlanningSlots:
    def test_planning_slots0(self, guv, xlsx, guvcapfd):
        guv.cd(guv.semester)
        guv("planning_slots").succeed()
        guvcapfd.stdout_search(
            ".  planning_slots"
        )
        for uv in guv.uvs:
            assert (guv.cwd / uv / "generated" / "planning.xlsx").is_file()

        uv = guv.uvs[0]
        doc = xlsx.tabular(guv.cwd / uv / "generated" / "planning.xlsx")
        doc.check_columns(
            "Activité",
            "Jour",
            "Heure début",
            "Heure fin",
            "Semaine",
            "Locaux",
            "Lib. créneau",
            "Intervenants",
            "Responsable",
            "date",
            "num",
            "numAB",
            "nweek",
        )
