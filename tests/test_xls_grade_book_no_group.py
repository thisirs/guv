import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_xls_grade_book_no_group_1(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("config_gradebook_test1.yaml", "documents")
    guv(
        "xls_grade_book_no_group --name Test1 --marking-scheme documents/config_gradebook_test1.yaml"
    ).succeed()
    guv.check_output_file(guv.cwd / "generated" / "Test1_gradebook.xlsx")
    guvcapfd.no_warning()


@path_dependency("test_xls_student_data")
def test_xls_grade_book_no_group_2(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("config_gradebook_test1.yaml", "documents")
    guv.copy_file("config_gradebook_test2.yaml", "documents")
    guv(
        "xls_grade_book_no_group --name Test2 --marking-scheme documents/config_gradebook_test1.yaml,documents/config_gradebook_test2.yaml"
    ).succeed()
    guv.check_output_file(guv.cwd / "generated" / "Test2_gradebook.xlsx")
    guvcapfd.no_warning()


@path_dependency("test_xls_student_data")
def test_xls_grade_book_no_group_3(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("config_gradebook_test3.yaml", "documents")
    guv(
        "xls_grade_book_no_group --name Test3 --marking-scheme documents/config_gradebook_test3.yaml"
    ).succeed()
    guv.check_output_file(guv.cwd / "generated" / "Test3_gradebook.xlsx")
    guvcapfd.no_warning()
