import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_xls_grade_book_nogroup(guv):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv(
        "xls_grade_book_no_group --name Test"
    ).succeed()
    assert (guv.cwd / "generated" / "Test_gradebook.xlsx").is_file()
