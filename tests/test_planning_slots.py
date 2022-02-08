import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_week_slots", name="test_planning_slots")
class TestPlanningSlots:
    def test_planning_slots0(self, guv, xlsx, guvcapfd):
        guv.cd(guv.semester)
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
                "%s": {
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
            """ % guv.semester
        )

        guv("planning_slots").succeed()
        guvcapfd.stdout_search(
            ".  planning_slots"
        )
        assert (guv.cwd / "SY02" / "generated" / "planning.xlsx").is_file()
        assert (guv.cwd / "SY09" / "generated" / "planning.xlsx").is_file()

        doc = xlsx.tabular(guv.cwd / "SY02" / "generated" / "planning.xlsx")
        doc.check_columns(
            "Activité",
            "Jour",
            "Heure début",
            "Heure fin",
            "Semaine",
            "Locaux",
            "Lib. créneau",
            "Intervenants",
            "Responsable",
            "date",
            "num",
            "numAB",
            "nweek",
        )

    def test_planning_slots1(self, guv, xlsx, guvcapfd):
        guv("planning_slots").succeed()
        guvcapfd.stdout_search(
            "-- planning_slots"
        )

        guv.change_config(
            f"""PLANNINGS["{guv.semester}"]["PL_BEG"] = date(2020, 9, 14)"""
        )
        guv("planning_slots").succeed()
        guvcapfd.stdout_search(
            ".  planning_slots"
        )

        guv("planning_slots").succeed()
        guvcapfd.stdout_search(
            "-- planning_slots"
        )
