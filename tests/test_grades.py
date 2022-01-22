import pytest
from pathlib import Path


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_csv_for_upload(semester_dir):
    semester_dir.change_relative_cwd("A2020", "SY02")
    ret = semester_dir.run_cli(
        "csv_for_upload"
    )

    assert ret != 0
    semester_dir.assert_out_search(
        
    )
