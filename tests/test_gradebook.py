import pytest
from pathlib import Path


# @pytest.mark.use_tree.with_args("test_students")
# def test_xls_grade_sheet(semester_dir):
#     semester_dir.copy_file("config_jury_test.yaml", "documents")
#     result = semester_dir.run_cli(
#         "xls_grade_sheet",
#         "jury",
#         "--name",
#         "test",
#         "--config",
#         "documents/config_jury_test.yaml"
#     )
#     assert result == 0
#     assert Path(semester_dir.cwd, "documents", "test_gradebook.xlsx").is_file()
