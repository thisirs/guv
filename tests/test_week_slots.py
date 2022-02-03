import pytest
from conftest import path_dependency


@path_dependency("test_utc_uv_list_to_csv", name="test_week_slots")
class TestWeekSlots:
    @pytest.mark.parametrize("uv", ["SY02", "SY09"])
    def test_week_slots(self, guv, xlsx, uv):
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
            "Type créneau",
            "Lib. créneau",
            "Intervenants",
            "Responsable",
        )


