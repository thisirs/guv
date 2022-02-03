import pytest
from conftest import path_dependency


@path_dependency("test_xls_student_data")
def test_pdf_attendance_full(guv, guvcapfd):
    guv.cd(guv.semester, "SY02")
    guv("pdf_attendance_full -n 14").succeed()
    assert (guv.cwd / "generated" / "Feuille_de_présence_all_full.pdf").is_file()
    guvcapfd.stdout_search(".  pdf_attendance_full")


@path_dependency("test_xls_student_data")
def test_pdf_attendance_full2(guv, guvcapfd):
    guv.cd(guv.semester, "SY02")
    guv("pdf_attendance_full -g TD -n 14").succeed()
    assert (guv.cwd / "generated" / "Feuille_de_présence_TD_full.zip").is_file()
    guvcapfd.stdout_search(".  pdf_attendance_full")
