import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_createsemester_old", cache=True, propagate_suffix=True)
def test_utc_uv_list_to_csv_old(guv_old, guvcapfd):
    "Test de traitement du fichier pdf des créneaux"

    guv_old.cd(guv_old.semester)
    guv_old("utc_uv_list_to_csv", input="A\nA\n").succeed()

    assert (guv_old.cwd / "documents" / "UTC_UV_list.csv").is_file()
    guvcapfd.stdout_search(". utc_uv_list_to_csv")
    guvcapfd.no_warning()
    guvcapfd.reset()

    guv_old("utc_uv_list_to_csv").succeed()
    guvcapfd.stdout_search("-- utc_uv_list_to_csv")
    guvcapfd.no_warning()


@path_dependency("test_createsemester", cache=True)
def test_utc_uv_list_to_csv(guv, guvcapfd):
    "Test de traitement du fichier pdf des créneaux"

    guv.cd(guv.semester)
    guv("utc_uv_list_to_csv", input="A\nA\n").succeed()

    assert (guv.cwd / "documents" / "UTC_UV_list.csv").is_file()
    guvcapfd.stdout_search(". utc_uv_list_to_csv")
    guvcapfd.no_warning()
    guvcapfd.reset()

    guv("utc_uv_list_to_csv").succeed()
    guvcapfd.stdout_search("-- utc_uv_list_to_csv")
    guvcapfd.no_warning()
