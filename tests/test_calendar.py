from pathlib import Path
import pytest


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_cal_uv(semester_dir):
    semester_dir.change_relative_cwd("A2020")
    ret = semester_dir.run_cli(
        "cal_uv"
    )
    semester_dir.assert_out_search(
        ".  cal_uv:A2020_SY02",
        "Écriture du fichier `SY02/documents/calendrier_hebdomadaire.pdf`",
        ".  cal_uv:A2020_SY09",
        "Écriture du fichier `SY09/documents/calendrier_hebdomadaire.pdf`",
    )

@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_cal_inst(semester_dir):
    semester_dir.change_relative_cwd("A2020", "SY02")
    ret = semester_dir.run_cli(
        "cal_inst"
    )
    assert ret != 0
    semester_dir.assert_out_search(
        "La variable 'DEFAULT_INSTRUCTOR' est incorrecte",
    )
    semester_dir.change_config(DEFAULT_INSTRUCTOR="Foo")
    ret = semester_dir.run_cli(
        "cal_inst"
    )
    assert ret == 0
    semester_dir.assert_out_search(
        "Écriture du fichier ``"
    )
