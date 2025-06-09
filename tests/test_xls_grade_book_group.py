import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_xls_grade_book_group(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("config_gradebook_test1.yaml", "documents")
    guv(
        "xls_grade_book_group --name Test -g Tutorial --marking-scheme documents/config_gradebook_test1.yaml"
    ).succeed()
    guv.check_output_file(guv.cwd / "generated" / "Test_gradebook.xlsx")
    guvcapfd.no_warning()
