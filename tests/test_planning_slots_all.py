import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_planning_slots")
def test_planning_slots_all(guv, xlsx, guvcapfd):
    guv.cd(guv.semester)
    assert not (guv.cwd / "generated" / "planning_all.xlsx").exists()
    guv("planning_slots_all").succeed()
    assert (guv.cwd / "generated" / "planning_all.xlsx").is_file()
    guvcapfd.stdout_search(".  planning_slots_all")

    doc = xlsx.tabular(guv.cwd / "generated" / "planning_all.xlsx")
    doc.check_columns(
        "Code enseig.",
        "Planning",
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
        "date",
        "num",
        "numAB",
        "nweek",
    )

