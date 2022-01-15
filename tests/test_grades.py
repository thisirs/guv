import pytest
from pathlib import Path


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_csv_for_upload(semester_dir):
    pass
