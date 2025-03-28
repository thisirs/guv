import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_csv_create_groups(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv("csv_create_groups").failed()

    guv("csv_create_groups Projet1 --group-size 3").succeed()
    assert (guv.cwd / "generated" / "Projet1_groups.csv").is_file()

    guv("csv_create_groups Projet2 --proportions 2 2").succeed()
    assert (guv.cwd / "generated" / "Projet2_groups.csv").is_file()

    guv("csv_create_groups Projet3 --proportions .5 .5 --names First Second")
    assert (guv.cwd / "generated" / "Projet3_groups.csv").is_file()

    guv("csv_create_groups Projet4 --group-size 3 --grouping group_1")
    assert (guv.cwd / "generated" / "Projet4_groups.csv").is_file()

    guv("csv_create_groups Projet5 --proportions .5 .5 --names First Second --affinity-groups group_1")
    assert (guv.cwd / "generated" / "Projet5_groups.csv").is_file()

    guv("csv_create_groups Projet6 --proportions .5 .5 --names First Second --other-groups group_2")
    assert (guv.cwd / "generated" / "Projet6_groups.csv").is_file()

