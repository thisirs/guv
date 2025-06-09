import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_xls_grade_book_jury(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("config_jury_test.yaml", "documents")
    guv(
        "xls_grade_book_jury --name Jury --config documents/config_jury_test.yaml"
    ).succeed()
    guv.check_output_file(guv.cwd / "generated" / "Jury_gradebook.xlsx")
    guvcapfd.no_warning()
