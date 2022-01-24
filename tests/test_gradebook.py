import pytest
from pathlib import Path


@pytest.mark.cache
@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_config_docs(semester_dir):
    semester_dir.change_relative_cwd("A2020", "SY02")
    semester_dir.change_config("""
    DOCS.apply_df(lambda df: df.assign(grade1=1))
    """)

    semester_dir.run_cli()


@pytest.mark.use_tree.with_args("test_config_docs")
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
    assert Path(semester_dir.cwd, "generated", "Jury_gradebook.xlsx").is_file()
