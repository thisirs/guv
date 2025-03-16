import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_week_slots")
def test_cal_uv(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("cal_uv").succeed()
    assert (guv.cwd / "documents" / "calendrier_hebdomadaire.pdf").is_file()
    guvcapfd.stdout_search(".  cal_uv")
    guvcapfd.no_warning()


@path_dependency("test_week_slots")
def test_cal_uv0(guv, guvcapfd):
    guv.cd(guv.semester)
    guv("cal_uv").succeed()
    for uv in guv.uvs:
        assert (guv.cwd / uv / "documents" / "calendrier_hebdomadaire.pdf").is_file()
    guvcapfd.stdout_search(".  cal_uv")
    guvcapfd.no_warning()
