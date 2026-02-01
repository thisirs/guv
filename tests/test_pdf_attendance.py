import pytest
from pytest_path_dependency import path_dependency


@path_dependency("test_xls_student_data")
def test_pdf_attendance(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("pdf_attendance").succeed()
    guv.check_output_file(guv.cwd / "generated" / "Attendance_sheet_all.pdf")
    guvcapfd.stdout_search(".  pdf_attendance")
    guvcapfd.no_warning()

@path_dependency("test_xls_student_data")
def test_pdf_attendance2(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("pdf_attendance -t foo").succeed()
    guv.check_output_file(guv.cwd / "generated" / "foo_all.pdf")
    guvcapfd.stdout_search(".  pdf_attendance")
    guvcapfd.no_warning()

@path_dependency("test_xls_student_data")
def test_pdf_attendance3(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("pdf_attendance -g Tutorial").succeed()
    guv.check_output_file(guv.cwd / "generated" / "Attendance_sheet_Tutorial.zip")
    guvcapfd.stdout_search(".  pdf_attendance")
    guvcapfd.no_warning()

@path_dependency("test_xls_student_data")
def test_pdf_attendance4(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("pdf_attendance -t foo -g Tutorial").succeed()
    guv.check_output_file(guv.cwd / "generated" / "foo_Tutorial.zip")
    guvcapfd.stdout_search(".  pdf_attendance")
    guvcapfd.no_warning()
