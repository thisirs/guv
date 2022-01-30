import pytest
from conftest import path_dependency


@path_dependency("test_xls_student_data")
def test_pdf_attendance_full(guv):
    guv.cd("A2020", "SY02")
    guv("pdf_attendance_full -g TD -n 14").succeed()
    assert (guv.cwd / "generated" / "attendance_TD_full.zip").is_file()
