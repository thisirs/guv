import pytest
from conftest import path_dependency


@path_dependency("test_csv_inscrits")
def test_xls_student_data0(guv):
    "Test du traitement des 3 fichiers de données étudiants"

    guv.cd("A2020", "SY02")
    guv.copy_file("inscrits.raw", "documents")
    guv.copy_file("extraction_enseig_note.XLS", "documents")
    guv.copy_file("SY02 Notes.xlsx", "documents")

    guv.change_config(ENT_LISTING="documents/extraction_enseig_note.XLS")
    guv.change_config(AFFECTATION_LISTING="documents/inscrits.raw")
    guv.change_config(MOODLE_LISTING="documents/SY02 Notes.xlsx")

    guv("xls_student_data").succeed()
    assert (guv.cwd / "generated" / "student_data.xlsx").is_file()

    guv("xls_student_data_merge").succeed()
    assert (guv.cwd / "effectif.xlsx").is_file()


@path_dependency("test_xls_student_data0", cache=True)
def test_xls_student_data(guv):
    guv.cd("A2020", "SY02")
    guv.change_config("""
    DOCS.apply_df(lambda df: df.assign(grade1=1))
    DOCS.apply_df(lambda df: df.assign(ects="A"))
    """)

    guv().succeed()
