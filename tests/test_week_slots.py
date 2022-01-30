import pytest
from conftest import path_dependency


@path_dependency("test_utc_uv_list_to_csv", name="test_week_slots")
class TestWeekSlots:
    @pytest.mark.parametrize("uv", ["SY02", "SY09"])
    def test_week_slots(self, guv, xlsx, uv):
        guv.cd("A2020")
        guv()
        assert (guv.cwd / uv / "documents" / "planning_hebdomadaire.xlsx").is_file()

        doc = xlsx(guv.cwd / uv / "documents" / "planning_hebdomadaire.xlsx")
        doc.columns(
            "Activité",
            "Jour",
            "Heure début",
            "Heure fin",
            "Semaine",
            "Locaux",
            "Type créneau",
            "Lib. créneau",
            "Intervenants",
            "Responsable"
        )

        guv.store(**{f"num_slots_{uv}": doc.nrow})
