import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_planning_slots")
def test_ical_uv(guv, guvcapfd):
    guv.cd(guv.semester, "SY02")
    guv("ical_uv").succeed()
    assert (guv.cwd / "documents" / "ics.zip").is_file()
    guvcapfd.stdout_search(".  ical_uv")


@path_dependency("test_planning_slots")
def test_ical_uv0(guv, guvcapfd):
    guv.cd(guv.semester)
    guv("ical_uv").succeed()
    assert (guv.cwd / "SY02" / "documents" / "ics.zip").is_file()
    assert (guv.cwd / "SY09" / "documents" / "ics.zip").is_file()
    guvcapfd.stdout_search(".  ical_uv")
