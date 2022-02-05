import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_planning_slots")
def test_json_restriction(guv, guvcapfd):
    guv.cd(guv.semester, "SY02")
    guv("json_restriction").succeed()

    assert (guv.cwd / "generated" / "moodle_restrictions_TP.json").is_file()
    guvcapfd.stdout_search(".  json_restriction")
