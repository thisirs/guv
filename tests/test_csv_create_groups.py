import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_csv_create_groups(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv("csv_create_groups").failed()

    guv("csv_create_groups Projet1 --group-size 3").succeed()
    assert (guv.cwd / "generated" / "Projet1_groups.csv").is_file()
