from pathlib import Path
import pytest


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_csv_exam_groups(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_csv_groups(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_csv_moodle_groups(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_csv_groups_groupings(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_zoom_breakout_rooms(semester_dir):
    pass
