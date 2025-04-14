import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_utc_uv_list_to_csv")
def test_ical_slots(guv):
    semester = guv.semester
    guv.cd(guv.semester)

    guv(f"ical_slots -p {semester} -s 'Lundi 8:00' -c Cours")
    assert (guv.cwd / "generated" / f"slots_{semester}_Cours.ics").is_file()
