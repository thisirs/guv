import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_xls_grade_book_jury(guv):
    guv.cd(guv.semester, "SY02")
    guv.copy_file("config_jury_test.yaml", "documents")
    guv(
        "xls_grade_book_jury --name Jury --config documents/config_jury_test.yaml"
    ).succeed()
    assert (guv.cwd / "generated" / "Jury_gradebook.xlsx").is_file()
