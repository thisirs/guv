import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_xls_student_data")
@pytest.mark.parametrize("filename", ("moodle_export_group_v1.xlsx", "moodle_export_group_v2.xlsx"))
def test_aggregate_moodle_groups(guv, xlsx, guvcapfd, filename):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file(filename, "documents")

    guv.change_config(f"""
    DOCS.aggregate_moodle_groups("documents/{filename}", "Projet")
    """)

    doc = xlsx.tabular(guv.cwd / "effectif.xlsx")
    columns_before = set(doc.df.columns)

    guv().succeed()

    doc = xlsx.tabular(guv.cwd / "effectif.xlsx")
    columns_after = set(doc.df.columns)

    assert(columns_after - columns_before == {"Projet"})
