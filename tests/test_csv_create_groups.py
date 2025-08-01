import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
def test_csv_create_groups(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv("csv_create_groups").failed()

    guv("csv_create_groups Projet1 --group-size 3").succeed()
    guv.check_output_file(guv.cwd / "generated" / "Projet1_groups.csv")
    guvcapfd.no_warning()
    guvcapfd.reset()

    guv("csv_create_groups Projet2 --proportions 2 2").succeed()
    guv.check_output_file(guv.cwd / "generated" / "Projet2_groups.csv")
    guvcapfd.no_warning()
    guvcapfd.reset()

    guv("csv_create_groups Projet3 --proportions .5 .5 --names First Second")
    guv.check_output_file(guv.cwd / "generated" / "Projet3_groups.csv")
    guvcapfd.no_warning()
    guvcapfd.reset()

    guv("csv_create_groups Projet4 --group-size 3 --grouping group_1")
    guv.check_output_file(guv.cwd / "generated" / "Projet4_groups.csv")
    guvcapfd.no_warning()
    guvcapfd.reset()

    guv("csv_create_groups Projet5 --proportions .5 .5  --names First Second --affinity-groups group_1")
    guv.check_output_file(guv.cwd / "generated" / "Projet5_groups.csv")
    guvcapfd.no_warning()
    guvcapfd.reset()

    guv("csv_create_groups Projet6 --num-groups 4 --names First Second Third Fourth --other-groups group_2")
    guv.check_output_file(guv.cwd / "generated" / "Projet6_groups.csv")
    guvcapfd.no_warning()
    guvcapfd.reset()

