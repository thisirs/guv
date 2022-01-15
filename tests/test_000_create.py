from pathlib import Path
import pytest


def test_createsemester_createuv(semester_dir):
    "Test de createsemester et createuv"

    result = semester_dir.run_cli("createsemester", "A2020")
    assert result == 0
    assert Path(semester_dir.cwd, "A2020").is_dir()
    assert Path(semester_dir.cwd, "A2020", "config.py").is_file()
    semester_dir.change_relative_cwd("A2020")

    result = semester_dir.run_cli("createuv", "SY02", "SY09")
    assert result == 0
    assert Path(semester_dir.cwd, "SY02").is_dir()
    assert Path(semester_dir.cwd, "SY02", "config.py").is_file()
    assert Path(semester_dir.cwd, "SY09").is_dir()
    assert Path(semester_dir.cwd, "SY09", "config.py").is_file()


@pytest.mark.cache
def test_createsemester(semester_dir):
    "Test de createsemester avec option uv"

    result = semester_dir.run_cli("createsemester", "A2020", "--uv", "SY02", "SY09")
    assert result == 0
    assert Path(semester_dir.cwd, "A2020").is_dir()
    assert Path(semester_dir.cwd, "A2020", "config.py").is_file()
    semester_dir.change_relative_cwd("A2020")
    assert Path(semester_dir.cwd, "SY02").is_dir()
    assert Path(semester_dir.cwd, "SY02", "config.py").is_file()
    assert Path(semester_dir.cwd, "SY09").is_dir()
    assert Path(semester_dir.cwd, "SY09", "config.py").is_file()
