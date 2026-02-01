import pytest
from pytest_path_dependency import path_dependency


@path_dependency("test_xls_student_data")
def test_pdf_attendance_full(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("pdf_attendance_full -n 14").succeed()
    guv.check_output_file(guv.cwd / "generated" / "Attendance_sheet_all_full.pdf")
    guvcapfd.stdout_search(".  pdf_attendance_full")
    guvcapfd.no_warning()


@path_dependency("test_xls_student_data")
def test_pdf_attendance_full2(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("pdf_attendance_full -g Tutorial -n 14").succeed()
    guv.check_output_file(guv.cwd / "generated" / "Attendance_sheet_Tutorial_full.zip")
    guvcapfd.stdout_search(".  pdf_attendance_full")
    guvcapfd.no_warning()
