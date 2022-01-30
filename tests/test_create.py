import pytest
from conftest import path_dependency

def test_createsemester_createuv(guv, guvcapfd):
    "Test de createsemester et createuv"

    guv("createsemester A2020").succeed()
    assert (guv.cwd / "A2020").is_dir()
    assert (guv.cwd / "A2020" / "config.py").is_file()
    guv.cd("A2020")

    guv("createuv SY02 SY09").succeed()
    assert (guv.cwd / "SY02").is_dir()
    assert (guv.cwd / "SY02" / "config.py").is_file()
    assert (guv.cwd / "SY09").is_dir()
    assert (guv.cwd / "SY09" / "config.py").is_file()

    guvcapfd.stdout_search("Création")


@path_dependency
def test_createsemester(guv):
    "Test de createsemester avec option uv"

    guv("createsemester A2020 --uv SY02 SY09").succeed()
    assert (guv.cwd / "A2020").is_dir()
    assert (guv.cwd / "A2020" / "config.py").is_file()

    guv.cd("A2020")
    assert (guv.cwd / "SY02").is_dir()
    assert (guv.cwd / "SY02" / "config.py").is_file()
    assert (guv.cwd / "SY09").is_dir()
    assert (guv.cwd / "SY09" / "config.py").is_file()
