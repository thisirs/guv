import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_csv_for_upload(guv, csv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("csv_for_upload -g grade1").succeed()
    assert (guv.cwd / "generated" / "grade1_ENT.csv").is_file()

    doc = csv(guv.cwd / "generated" / "grade1_ENT.csv", sep=";", encoding="latin-1")
    doc.check_columns(
        "Nom",
        "Prénom",
        "Login",
        "Note",
        "Commentaire",
    )
    guvcapfd.stdout_search(".  csv_for_upload")
    guvcapfd.no_warning()


@path_dependency("test_xls_student_data")
def test_csv_for_upload2(guv, csv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("csv_for_upload -g ects --ects").succeed()
    assert (guv.cwd / "generated" / "ects_ENT.csv").is_file()

    doc = csv(guv.cwd / "generated" / "ects_ENT.csv", sep=";", encoding="latin-1")
    doc.check_columns(
        "Nom",
        "Prénom",
        "Login",
        "Note",
    )
    guvcapfd.stdout_search(".  csv_for_upload")
    guvcapfd.no_warning()
