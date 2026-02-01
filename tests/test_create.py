import pytest
from pytest_path_dependency import path_dependency


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

    guvcapfd.stdout_search("Creating")


@path_dependency
def test_createsemester(guv):
    "Test de createsemester avec option uv"

    guv(f"createsemester {guv.semester} --uv {' '.join(guv.uvs)}").succeed()
    assert (guv.cwd / guv.semester).is_dir()
    assert (guv.cwd / guv.semester / "config.py").is_file()

    guv.cd(guv.semester)
    for uv in guv.uvs:
        assert (guv.cwd / uv).is_dir()
        assert (guv.cwd / uv / "config.py").is_file()
