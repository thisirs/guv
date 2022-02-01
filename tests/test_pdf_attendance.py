import pytest
from conftest import path_dependency


@path_dependency("test_xls_student_data")
def test_pdf_attendance(guv, guvcapfd):
    guv.cd("A2020", "SY02")
    guv("pdf_attendance").succeed()
    assert (guv.cwd / "generated" / "Feuille_de_présence_all.pdf").is_file()
    guvcapfd.stdout_search(".  pdf_attendance")

@path_dependency("test_xls_student_data")
def test_pdf_attendance2(guv, guvcapfd):
    guv.cd("A2020", "SY02")
    guv("pdf_attendance -t foo").succeed()
    assert (guv.cwd / "generated" / "foo_all.pdf").is_file()
    guvcapfd.stdout_search(".  pdf_attendance")


@path_dependency("test_xls_student_data")
def test_pdf_attendance3(guv, guvcapfd):
    guv.cd("A2020", "SY02")
    guv("pdf_attendance -g TD").succeed()
    assert (guv.cwd / "generated" / "Feuille_de_présence_TD.zip").is_file()
    guvcapfd.stdout_search(".  pdf_attendance")


@path_dependency("test_xls_student_data")
def test_pdf_attendance4(guv, guvcapfd):
    guv.cd("A2020", "SY02")
    guv("pdf_attendance -t foo -g TD").succeed()
    assert (guv.cwd / "generated" / "foo_TD.zip").is_file()
    guvcapfd.stdout_search(".  pdf_attendance")
