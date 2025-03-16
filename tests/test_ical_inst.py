import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_planning_slots")
class TestIcalInst:
    def test_ical_inst0(self, guv, guvcapfd):
        guv.cd(guv.semester)
        guv("ical_inst")
        guvcapfd.stdout_search("La variable 'DEFAULT_INSTRUCTOR' est incorrecte")
        guvcapfd.no_warning()

    def test_ical_inst1(self, guv, guvcapfd):
        guv.change_config(DEFAULT_INSTRUCTOR="Bob Marley")
        guv("ical_inst")
        guvcapfd.stdout_search("Intervenant inconnu")
        guvcapfd.no_warning()

    def test_ical_inst2(self, guv, xlsx, guvcapfd):
        uv = guv.uvs[0]
        with xlsx.tabular(
            guv.cwd / uv / "documents" / "planning_hebdomadaire.xlsx",
            sheet_name="Intervenants",
        ) as doc:
            doc.df["Intervenants"] = "Bob Marley"
        guv("ical_inst")
        guvcapfd.stdout_search("Écriture du fichier `generated/Bob_Marley.ics`")
        guvcapfd.no_warning()
