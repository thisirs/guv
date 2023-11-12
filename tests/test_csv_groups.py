import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_csv_groups(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv("csv_groups").succeed()

    assert (guv.cwd / "generated" / "Cours_group_moodle.csv").is_file()
    assert (guv.cwd / "generated" / "TD_group_moodle.csv").is_file()
