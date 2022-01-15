from pathlib import Path
import pytest


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_html_inst(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_html_table(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_json_restriction(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_json_group(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_csv_create_groups(semester_dir):
    pass


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_fetch_group_id(semester_dir):
    pass
