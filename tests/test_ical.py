from pathlib import Path
import pytest


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_ical_inst(semester_dir):
    semester_dir.change_relative_cwd("A2020")

    ret = semester_dir.run_cli(
        "ical_inst"
    )
    assert ret != 0
    semester_dir.assert_out_search(
        "La variable 'DEFAULT_INSTRUCTOR' est incorrecte",
    )

    semester_dir.change_config(DEFAULT_INSTRUCTOR="Foo")
    ret = semester_dir.run_cli(
        "ical_inst"
    )
    assert ret != 0
    semester_dir.assert_out_search(
        "La variable `PL_BEG` n'a pas pu être trouvée"
    )


    semester_dir.change_config(DEFAULT_INSTRUCTOR="Foo")
    semester_dir.change_config(
        """
        from datetime import date
        from guv.helpers import skip_week, skip_range

        # Jours fériés
        ferie = [date(2020, 10, 15), date(2020, 11, 11)]

        # Première semaine sans TD/TP
        debut = skip_week(date(2020, 9, 7))

        # Semaine des médians
        median = skip_range(date(2020, 11, 3), date(2020, 11, 9))

        # Vacances
        vacances_toussaint = skip_range(date(2020, 10, 26), date(2020, 10, 31))
        vacances_noel = skip_range(date(2020, 12, 23), date(2021, 1, 3))
        vacances = vacances_toussaint + vacances_noel

        # Semaine des finals
        final = skip_range(date(2021, 1, 9), date(2021, 1, 16))

        PLANNINGS={
            "A2020": {
                "UVS": ["SY09", "SY02"],
                "PL_BEG": date(2020, 9, 7),
                "PL_END": date(2021, 1, 16),
                "TURN": {
                    date(2020, 10, 19): "Jeudi",
                    date(2020, 11, 10): "Mercredi",
                    date(2020, 12, 23): "Samedi",
                },
                "SKIP_DAYS_C": ferie + vacances + median + final,
                "SKIP_DAYS_D": ferie + vacances + debut + median + final,
                "SKIP_DAYS_T": ferie + vacances + debut + final
            }
        }
        """
    )
    ret = semester_dir.run_cli(
        "ical_inst"
    )
    assert ret != 0

    semester_dir.write_excel("SY02/documents/planning_hebdomadaire.xlsx", "I2", "Foo")
    ret = semester_dir.run_cli(
        "ical_inst"
    )
    assert ret == 0
    semester_dir.assert_out_search(
        "Écriture du fichier `generated/Foo_A2020.ics`"
    )

    semester_dir.write_excel("SY09/documents/planning_hebdomadaire.xlsx", "I2", "Foo")
    ret = semester_dir.run_cli(
        "ical_inst"
    )
    assert ret == 0
    semester_dir.assert_out_search(
        "Écrasement du fichier `generated/Foo_A2020.ics`"
    )
