import pytest
from conftest import path_dependency


def test_createsemester_createuv(guv, guvcapfd):
    "Test de createsemester et createuv"

    guv(f"createsemester {guv.semester}").succeed()
    assert (guv.cwd / guv.semester).is_dir()
    assert (guv.cwd / guv.semester / "config.py").is_file()
    guv.cd(guv.semester)

    guv("createuv SY02 SY09").succeed()
    assert (guv.cwd / "SY02").is_dir()
    assert (guv.cwd / "SY02" / "config.py").is_file()
    assert (guv.cwd / "SY09").is_dir()
    assert (guv.cwd / "SY09" / "config.py").is_file()

    guvcapfd.stdout_search("Création")


@path_dependency
def test_createsemester(guv):
    "Test de createsemester avec option uv"

    guv(f"createsemester {guv.semester} --uv SY02 SY09").succeed()
    assert (guv.cwd / guv.semester).is_dir()
    assert (guv.cwd / guv.semester / "config.py").is_file()

    guv.cd(guv.semester)
    assert (guv.cwd / "SY02").is_dir()
    assert (guv.cwd / "SY02" / "config.py").is_file()
    assert (guv.cwd / "SY09").is_dir()
    assert (guv.cwd / "SY09" / "config.py").is_file()
