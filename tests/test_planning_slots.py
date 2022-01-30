import pytest
from conftest import path_dependency


@path_dependency("test_week_slots")
def test_planning_slots0(guv, guvcapfd):
    guv.cd("A2020")
    guv("planning_slots").failed()
    guvcapfd.stdout_search(
        "La variable `PL_BEG` n'a pas pu être trouvée"
    )


@path_dependency("test_week_slots")
def test_planning_slots(guv, xlsx):
    guv.cd("A2020")
    guv.change_config(
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

    guv("planning_slots").succeed()
    assert (guv.cwd / "SY02" / "generated" / "planning.xlsx").is_file()
    assert (guv.cwd / "SY09" / "generated" / "planning.xlsx").is_file()

    doc = xlsx(guv.cwd / "SY02" / "generated" / "planning.xlsx")
    doc.columns(
        "Activité",
        "Jour",
        "Heure début",
        "Heure fin",
        "Semaine",
        "Locaux",
        "Type créneau",
        "Lib. créneau",
        "Intervenants",
        "Responsable",
        "date",
        "dayname",
        "num",
        "weekAB",
        "numAB",
        "nweek",
    )
