import pytest
from pathlib import Path

@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_xls_grade_sheet(semester_dir):
    semester_dir.change_relative_cwd("A2020", "SY02")
    semester_dir.copy_file("config_jury_test.yaml", "documents")
    result = semester_dir.run_cli(
        "xls_grade_book_jury",
        "--name",
        "Jury",
        "--config",
        "documents/config_jury_test.yaml"
    )
    assert result == 0
    assert Path(semester_dir.cwd, "documents", "Jury_gradebook.xlsx").is_file()
