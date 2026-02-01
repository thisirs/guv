import pytest
from pytest_path_dependency import path_dependency


@path_dependency("test_createsemester")
def test_csv_groups_groupings(guv, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv("csv_groups_groupings -G 3 -F Groupement_P1 -g 14 -f D##_P1_@").succeed()
    guv.check_output_file(guv.cwd / "generated" / "groups_groupings.csv")
    guvcapfd.no_warning()
    guvcapfd.reset()
