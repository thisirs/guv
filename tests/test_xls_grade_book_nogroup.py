import pytest
from conftest import path_dependency


@path_dependency("test_xls_student_data")
def test_xls_grade_book_nogroup(guv):
    guv.cd(guv.semester, "SY02")
    guv(
        "xls_grade_book_no_group --name Test"
    ).succeed()
    assert (guv.cwd / "generated" / "Test_gradebook.xlsx").is_file()
