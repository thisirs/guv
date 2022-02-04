import pytest
from conftest import path_dependency


@path_dependency("test_planning_slots")
class TestIcalInst:
    def test_ical_inst0(self, guv, guvcapfd):
        guv.cd(guv.semester)
        guv("ical_inst")
        guvcapfd.stdout_search("La variable 'DEFAULT_INSTRUCTOR' est incorrecte")

    def test_ical_inst1(self, guv, guvcapfd):
        guv.change_config(DEFAULT_INSTRUCTOR="Bob Marley")
        guv("ical_inst")
        guvcapfd.stdout_search("Intervenant inconnu")

    def test_ical_inst2(self, guv, xlsx, guvcapfd):
        with xlsx.tabular(
            guv.cwd / "SY02" / "documents" / "planning_hebdomadaire.xlsx",
            sheet_name="Intervenants",
        ) as doc:
            doc.df["Intervenants"] = "Bob Marley"
        guv("ical_inst")
        guvcapfd.stdout_search("Écriture du fichier `generated/Bob_Marley.ics`")
