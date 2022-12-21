import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_createsemester_old", cache=True)
def test_utc_uv_list_to_csv_old(guv_old, guvcapfd):
    "Test de traitement du fichier pdf des créneaux"

    guv_old.cd(guv_old.semester)
    guv_old.copy_file(guv_old.creneaux_uv, "documents")
    guv_old.change_config(CRENEAU_UV=f"documents/{guv_old.creneaux_uv}")
    guv_old("utc_uv_list_to_csv", input="A\n").succeed()

    assert (guv_old.cwd / "documents" / "UTC_UV_list.csv").is_file()
    guvcapfd.stdout_search(". utc_uv_list_to_csv")

    guv_old("utc_uv_list_to_csv").succeed()
    guvcapfd.stdout_search("-- utc_uv_list_to_csv")


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
