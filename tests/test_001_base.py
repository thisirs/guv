from pathlib import Path
import pytest


@pytest.mark.use_tree.with_args("test_createsemester")
def test_utc_uv_list_to_csv(semester_dir):
    ret = semester_dir.run_cli("utc_uv_list_to_csv")
    assert ret != 0
    semester_dir.assert_out_search(
        "La variable `CRENEAU_UV` doit être définie"
    )


@pytest.mark.cache
@pytest.mark.use_tree.with_args("test_createsemester")
def test_utc_uv_list_to_csv2(semester_dir, monkeypatch):
    "Test de traitement du fichier pdf des créneaux"

    monkeypatch.setattr("builtins.input", lambda _: "A")
    semester_dir.copy_file("Creneaux-UV_P20.pdf", "documents")
    semester_dir.change_config(CRENEAU_UV="documents/Creneaux-UV_P20.pdf")
    ret = semester_dir.run_func("utc_uv_list_to_csv")
    assert ret == 0
    assert Path(semester_dir.cwd, "documents", "UTC_UV_list.csv").is_file()
    semester_dir.assert_out_search(". utc_uv_list_to_csv")

    ret = semester_dir.run_cli(
        "utc_uv_list_to_csv"
    )
    assert ret == 0
    semester_dir.assert_out_search("-- utc_uv_list_to_csv")


@pytest.mark.use_tree.with_args(test_utc_uv_list_to_csv2)
def test_utc_uv_list_to_csv3(semester_dir):
    "Test de traitement du fichier AFFECTATION_LISTING"

    semester_dir.change_relative_cwd("A2020", "SY02")
    semester_dir.copy_file("inscrits.raw", "documents")
    semester_dir.change_config(AFFECTATION_LISTING="documents/inscrits.raw")
    ret = semester_dir.run_cli("csv_inscrits")
    assert ret == 0
    assert Path(semester_dir.cwd, "generated", "inscrits.csv").is_file()
    semester_dir.assert_out_search(". csv_inscrits")

    ret = semester_dir.run_cli("csv_inscrits")
    assert ret == 0
    semester_dir.assert_out_search("-- csv_inscrits")


@pytest.mark.cache
@pytest.mark.use_tree.with_args(test_utc_uv_list_to_csv2)
def test_xls_student_data(semester_dir):
    "Test du traitement des 3 fichiers de données étudiants"

    semester_dir.change_relative_cwd("A2020", "SY02")
    semester_dir.copy_file("inscrits.raw", "documents")
    semester_dir.copy_file("extraction_enseig_note.XLS", "documents")
    semester_dir.copy_file("SY02 Notes.xlsx", "documents")

    semester_dir.change_config(ENT_LISTING="documents/extraction_enseig_note.XLS")
    semester_dir.change_config(AFFECTATION_LISTING="documents/inscrits.raw")
    semester_dir.change_config(MOODLE_LISTING="documents/SY02 Notes.xlsx")

    ret = semester_dir.run_cli("xls_student_data")
    assert ret == 0
    assert Path(semester_dir.cwd, "generated", "student_data.xlsx").is_file()

    ret = semester_dir.run_cli("xls_student_data_merge")
    assert ret == 0
    assert Path(semester_dir.cwd, "effectif.xlsx").is_file()

    ret = semester_dir.run_cli("week_slots")



# @pytest.mark.use_tree.with_args(test_utc_uv_list_to_csv2)
# def test_week_slots(semester_dir):
#     semester_dir.change_relative_cwd("A2020", "SY02")
#     ret = semester_dir.run_cli("week_slots")
#     assert ret == 0
#     for uv in ["SY02", "SY09"]:
#         assert Path(
#             semester_dir.base_dir, uv, "documents", "intervenants.xlsx"
#         ).is_file()
