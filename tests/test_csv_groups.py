import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_csv_groups(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv("csv_groups").succeed()

    guv.check_output_file(guv.cwd / "generated" / "Lecture_group_moodle.csv")
    guv.check_output_file(guv.cwd / "generated" / "Tutorial_group_moodle.csv")
