import pytest
from conftest import path_dependency


@path_dependency("test_xls_student_data")
def test_pdf_attendance(guv):
    guv.cd("A2020", "SY02")
    guv("pdf_attendance -t foo -g TD").succeed()
    assert (guv.cwd / "generated" / "attendance_TD.zip").is_file()
