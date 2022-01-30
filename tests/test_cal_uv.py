import pytest
from conftest import path_dependency


@path_dependency("test_week_slots")
def test_cal_uv(guv):
    guv.cd("A2020", "SY02")
    guv("cal_uv").succeed()
    assert (guv.cwd / "documents" / "calendrier_hebdomadaire.pdf").is_file()


@path_dependency("test_week_slots")
def test_cal_uv(guv):
    guv.cd("A2020")
    guv("cal_uv").succeed()
    assert (guv.cwd / "SY02" / "documents" / "calendrier_hebdomadaire.pdf").is_file()
    assert (guv.cwd / "SY09" / "documents" / "calendrier_hebdomadaire.pdf").is_file()
