import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_createsemester")
def test_utc_uv_list_to_csv0(guv, guvcapfd):
    guv.cd(guv.semester)
    guv("utc_uv_list_to_csv").failed()
    guvcapfd.stdout_search(
        "La variable `CRENEAU_UV` doit être définie"
    )


@path_dependency("test_createsemester", cache=True)
def test_utc_uv_list_to_csv(guv, guvcapfd):
    "Test de traitement du fichier pdf des créneaux"

    guv.cd(guv.semester)
    guv.copy_file(guv.creneaux_uv, "documents")
    guv.change_config(CRENEAU_UV=f"documents/{guv.creneaux_uv}")
    guv("utc_uv_list_to_csv", input="A\n").succeed()

    assert (guv.cwd / "documents" / "UTC_UV_list.csv").is_file()
    guvcapfd.stdout_search(". utc_uv_list_to_csv")

    guv("utc_uv_list_to_csv").succeed()
    guvcapfd.stdout_search("-- utc_uv_list_to_csv")
