import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_planning_slots")
def test_ical_uv(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("ical_uv").succeed()
    assert (guv.cwd / "documents" / "ics.zip").is_file()
    guvcapfd.stdout_search(".  ical_uv")


@path_dependency("test_planning_slots")
def test_ical_uv0(guv, guvcapfd):
    guv.cd(guv.semester)
    guv("ical_uv").succeed()
    for uv in guv.uvs:
        assert (guv.cwd / uv / "documents" / "ics.zip").is_file()
    guvcapfd.stdout_search(".  ical_uv")
