import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_csv_inscrits", name="test_xls_student_data", cache=True)
def test_xls_student_data0(guv, guvcapfd):
    "Test du traitement des 3 fichiers de données étudiants"

    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("inscrits.raw", "documents")
    guv.copy_file("extraction_enseig_note.XLS", "documents")
    guv.copy_file("SY02 Notes.xlsx", "documents")

    guv.change_config(ENT_LISTING="documents/extraction_enseig_note.XLS")
    guv.change_config(AFFECTATION_LISTING="documents/inscrits.raw")
    guv.change_config(MOODLE_LISTING="documents/SY02 Notes.xlsx")

    guv("xls_student_data").succeed()
    guvcapfd.stdout_search(".  xls_student_data")
    assert (guv.cwd / "generated" / "student_data.xlsx").is_file()

    guv("xls_student_data_merge").succeed()
    guvcapfd.stdout_search(".  xls_student_data_merge")
    assert (guv.cwd / "effectif.xlsx").is_file()

    guv.change_config("""
    DOCS.apply_df(lambda df: df.assign(grade1=1))
    DOCS.apply_df(lambda df: df.assign(ects="A"))
    """)

    guv().succeed()
    guvcapfd.stdout_search(".  xls_student_data_merge")
