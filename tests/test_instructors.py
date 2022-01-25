from pathlib import Path
import pytest


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_xls_instructors(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_week_slots_all(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_xls_inst_details(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_xls_utp(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_week_slots(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_xls_emploi_du_temps(semester_dir):
    pass
