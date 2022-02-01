import pytest
from conftest import path_dependency


@path_dependency("test_xls_student_data")
def test_csv_for_upload(guv, csv, guvcapfd):
    guv.cd("A2020", "SY02")
    guv("csv_for_upload -g grade1").succeed()
    assert (guv.cwd / "generated" / "grade1_ENT.csv").is_file()

    doc = csv(guv.cwd / "generated" / "grade1_ENT.csv", sep=";")
    doc.columns(
        "Nom",
        "Prénom",
        "Login",
        "Note",
        "Commentaire",
    )
    guvcapfd.stdout_search(".  csv_for_upload")


@path_dependency("test_xls_student_data")
def test_csv_for_upload2(guv, csv, guvcapfd):
    guv.cd("A2020", "SY02")
    guv("csv_for_upload -g ects --ects").succeed()
    assert (guv.cwd / "generated" / "ects_ENT.csv").is_file()

    doc = csv(guv.cwd / "generated" / "ects_ENT.csv", sep=";")
    doc.columns(
        "Nom",
        "Prénom",
        "Login",
        "Note",
    )
    guvcapfd.stdout_search(".  csv_for_upload")
