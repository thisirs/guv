import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_planning_slots")
def test_json_restriction(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("json_restriction -c Cours").succeed()

    assert (guv.cwd / "generated" / "moodle_availability_restrictions_Cours.json").is_file()
    assert (guv.cwd / "generated" / "moodle_timings_restrictions_Cours.json").is_file()
    guvcapfd.stdout_search(".  json_restriction")
    # guvcapfd.no_warning()
