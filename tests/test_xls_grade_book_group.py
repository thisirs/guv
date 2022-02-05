import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_xls_grade_book_group(guv):
    guv.cd(guv.semester, "SY02")
    guv(
        "xls_grade_book_group --name Test -g TD"
    ).succeed()
    assert (guv.cwd / "generated" / "Test_gradebook.xlsx").is_file()
