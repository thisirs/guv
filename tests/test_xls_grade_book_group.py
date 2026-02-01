import pytest
from pytest_path_dependency import path_dependency


@path_dependency("test_xls_student_data")
def test_xls_grade_book_group_1(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("config_gradebook_test1.yaml", "documents")
    guv(
        "xls_grade_book_group --name Test_group_1 -g Tutorial --marking-scheme documents/config_gradebook_test1.yaml"
    ).succeed()
    guv.check_output_file(guv.cwd / "generated" / "Test_group_1_gradebook.xlsx")
    guvcapfd.no_warning()


@path_dependency("test_xls_student_data")
def test_xls_grade_book_group_2(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("config_gradebook_test1.yaml", "documents")
    guv.copy_file("config_gradebook_test2.yaml", "documents")
    guv(
        "xls_grade_book_group --name Test_group_2 -g Tutorial --marking-scheme documents/config_gradebook_test1.yaml,documents/config_gradebook_test2.yaml"
    ).succeed()
    guv.check_output_file(guv.cwd / "generated" / "Test_group_2_gradebook.xlsx")
    guvcapfd.no_warning()


@path_dependency("test_xls_student_data")
def test_xls_grade_book_group_3(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("config_gradebook_test3.yaml", "documents")
    guv(
        "xls_grade_book_group --name Test_group_3 -g Tutorial --marking-scheme documents/config_gradebook_test3.yaml"
    ).succeed()
    guv.check_output_file(guv.cwd / "generated" / "Test_group_3_gradebook.xlsx")
    guvcapfd.no_warning()
