import pytest
from conftest import path_dependency


@path_dependency("test_week_slots")
def test_week_slots_all(guv, guvcapfd, xlsx):
    guv.cd("A2020")
    guv("week_slots_all").succeed()
    assert (guv.cwd / "generated" / "planning_hebdomadaire.xlsx").is_file()
    guvcapfd.stdout_search(".  week_slots_all")

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

    guv("week_slots_all").succeed()
    guvcapfd.stdout_search("-- week_slots_all")
