import pytest
from conftest import path_dependency


@path_dependency("test_utc_uv_list_to_csv")
def test_csv_inscrits(guv, guvcapfd):
    "Test de traitement du fichier AFFECTATION_LISTING"

    guv.cd(guv.semester, "SY02")
    guv.copy_file("inscrits.raw", "documents")
    guv.change_config(AFFECTATION_LISTING="documents/inscrits.raw")
    guv("csv_inscrits").succeed()

    assert (guv.cwd / "generated" / "inscrits.csv").is_file()
    guvcapfd.stdout_search(". csv_inscrits")

    guv("csv_inscrits").succeed()
    guvcapfd.stdout_search("-- csv_inscrits")
