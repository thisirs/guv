import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_pdf_attendance(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("pdf_attendance").succeed()
    assert (guv.cwd / "generated" / "Attendance_sheet_all.pdf").is_file()
    guvcapfd.stdout_search(".  pdf_attendance")
    guvcapfd.no_warning()

@path_dependency("test_xls_student_data")
def test_pdf_attendance2(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("pdf_attendance -t foo").succeed()
    assert (guv.cwd / "generated" / "foo_all.pdf").is_file()
    guvcapfd.stdout_search(".  pdf_attendance")
    guvcapfd.no_warning()

@path_dependency("test_xls_student_data")
def test_pdf_attendance3(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("pdf_attendance -g Tutorial").succeed()
    assert (guv.cwd / "generated" / "Attendance_sheet_Tutorial.zip").is_file()
    guvcapfd.stdout_search(".  pdf_attendance")
    guvcapfd.no_warning()

@path_dependency("test_xls_student_data")
def test_pdf_attendance4(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("pdf_attendance -t foo -g Tutorial").succeed()
    assert (guv.cwd / "generated" / "foo_Tutorial.zip").is_file()
    guvcapfd.stdout_search(".  pdf_attendance")
    guvcapfd.no_warning()
