import pytest
from conftest import path_dependency


@path_dependency("test_planning_slots")
def test_planning_slots_all(guv, xlsx):
    guv.cd("A2020")
    assert not (guv.cwd / "generated" / "planning_all.xlsx").exists()
    guv("planning_slots_all").succeed()
    assert (guv.cwd / "generated" / "planning_all.xlsx").is_file()

    doc = xlsx(guv.cwd / "generated" / "planning_all.xlsx")
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
        "Responsable",
        "date",
        "num",
        "numAB",
        "nweek",
    )
