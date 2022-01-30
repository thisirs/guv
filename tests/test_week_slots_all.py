import pytest
from conftest import path_dependency


@path_dependency("test_week_slots")
def test_week_slots_all(guv, xlsx):
    guv.cd("A2020")
    guv("week_slots_all").succeed()
    assert (guv.cwd / "generated" / "planning_hebdomadaire.xlsx").is_file()

    doc = xlsx(guv.cwd / "generated" / "planning_hebdomadaire.xlsx")
    doc.columns(
        "Code enseig.",
        "Planning",
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
