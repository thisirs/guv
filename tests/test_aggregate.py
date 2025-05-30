import pytest
from tests.plugins.test_path import path_dependency


data = [
    ("moodle_export_choicegroup_en.xlsx")
]

@path_dependency("test_xls_student_data")
@pytest.mark.parametrize("filename", data)
def test_docs_aggregate_moodle_groups(guv, xlsx, guvcapfd, filename):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file(filename, "documents")

    guv.change_config(f"""
    DOCS.aggregate_moodle_groups("documents/{filename}", "Project")
    """)

    doc = xlsx.tabular(guv.cwd / "effectif.xlsx")
    columns_before = set(doc.df.columns)

    guv().succeed()

    doc = xlsx.tabular(guv.cwd / "effectif.xlsx")
    columns_after = set(doc.df.columns)

    assert(columns_after - columns_before == {"Project"})


data = [
        ("moodle_export_gradebook_en.xlsx", ("Note de médian (Real)", "Quiz: Quiz semaine 14 (Real)", "Assignment: Rendu du chapitre 1 : Modélisation (Real)"))
]

@path_dependency("test_xls_student_data")
@pytest.mark.parametrize("filename,keep", data)
def test_docs_aggregate_moodle_grades(guv, xlsx, guvcapfd, filename, keep):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file(filename, "documents")

    guv.change_config(f"""
    DOCS.aggregate_moodle_grades("documents/{filename}")
    """)

    doc = xlsx.tabular(guv.cwd / "effectif.xlsx")
    columns_before = set(doc.df.columns)

    guv().succeed()

    doc = xlsx.tabular(guv.cwd / "effectif.xlsx")
    columns_after = set(doc.df.columns)

    assert(columns_after - columns_before == set(keep))


@path_dependency("test_xls_student_data")
def test_docs_fillna_column(guv, xlsx):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv.change_config(f"""
    import numpy as np
    DOCS.apply_df(lambda df: df.assign(fillna_col=[1, 2, np.nan, 4, np.nan, 6, 7, 8]))
    DOCS.fillna_column("fillna_col", na_value=0)
    """)
    guv().succeed()

    doc = xlsx.tabular(guv.cwd / "effectif.xlsx")
    assert all(doc.df["fillna_col"].eq([1, 2, 0, 4, 0, 6, 7, 8]))


@path_dependency("test_xls_student_data")
def test_docs_fillna_column2(guv, xlsx):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv.change_config(f"""
    import numpy as np
    DOCS.apply_df(lambda df: df.assign(fillna_group=["G1", "G1", "G1", "G2", "G2", "G2", "G3", "G3"]))
    DOCS.apply_df(lambda df: df.assign(fillna_col=[np.nan, 2, np.nan, 4, np.nan, np.nan, 7, 7]))
    DOCS.fillna_column("fillna_col", group_column="fillna_group")
    """)
    guv().succeed()

    doc = xlsx.tabular(guv.cwd / "effectif.xlsx")
    assert all(doc.df["fillna_col"].eq([2, 2, 2, 4, 4, 4, 7, 7]))


@path_dependency("test_xls_student_data")
def test_docs_replace_regex(guv, xlsx):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv.change_config(r"""
    import numpy as np
    DOCS.apply_df(lambda df: df.assign(replace_regex_col=["gr1", "gr2", "gr3", "gr4", "group5", "group6", "group7", "group8"]))
    DOCS.replace_regex("replace_regex_col", (r"group([0-9])", r"gr\1"), (r"gr([0-9])", r"G\1"))
    """)
    guv().succeed()

    doc = xlsx.tabular(guv.cwd / "effectif.xlsx")
    assert all(doc.df["replace_regex_col"].eq(["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]))


@path_dependency("test_xls_student_data")
def test_docs_replace_column(guv, xlsx):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv.change_config(r"""
    import numpy as np
    DOCS.apply_df(lambda df: df.assign(replace_column_col=["gr1", "gr2", "gr3", "gr4", "group5", "group6", "group7", "group8"]))
    DOCS.replace_column("replace_column_col", {"group5": "gr5", "group6": "gr6"})
    """)
    guv().succeed()

    doc = xlsx.tabular(guv.cwd / "effectif.xlsx")
    assert all(doc.df["replace_column_col"].eq(["gr1", "gr2", "gr3", "gr4", "gr5", "gr6", "group7", "group8"]))


@path_dependency("test_xls_student_data")
def test_docs_apply_df(guv, xlsx):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv.change_config(r"""
    DOCS.apply_df(lambda df: df.assign(new_column=1))
    """)
    guv().succeed()


@path_dependency("test_xls_student_data")
def test_docs_apply_column(guv, xlsx):
    pass


@path_dependency("test_xls_student_data")
def test_docs_compute_new_column(guv, xlsx):
    pass


@path_dependency("test_xls_student_data")
def test_docs_add(guv, xlsx):
    pass


@path_dependency("test_xls_student_data")
def test_docs_aggregate(guv, xlsx):
    pass


@path_dependency("test_xls_student_data")
def test_docs_aggregate_self(guv, xlsx):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    with xlsx.tabular(guv.cwd / "effectif.xlsx") as tab:
        tab.df["Manual"] = 1

    guv.change_config("""DOCS.aggregate_self("Manual")""")

    guv().succeed()
    xlsx.tabular(guv.cwd / "effectif.xlsx").contains("Manual")


@path_dependency("test_xls_student_data")
def test_docs_aggregate_jury(guv, xlsx):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv.copy_file("config_jury_test.yaml", "documents")
    guv(
        "xls_grade_book_jury --name Jury --config documents/config_jury_test.yaml"
    ).succeed()
    filename = "generated/Jury_gradebook.xlsx"

    assert (guv.cwd / filename).is_file()

    guv.change_config(f"""
    DOCS.aggregate_jury("{filename}")
    """)

    guv().succeed()

    xlsx.tabular(guv.cwd / "effectif.xlsx").contains("ECTS grade", "Aggregated grade")


@path_dependency("test_xls_student_data")
def test_docs_aggregate_org(guv, xlsx):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    filename = "documents/org"
    guv.create_file(filename, """\
* Marco Bla
  Some remark
* Pierre Blahblahfoo
  Some other remark
""")

    guv.change_config(f"""
    DOCS.aggregate_org("{filename}", colname="Org")
    """)

    guv().succeed()
    xlsx.tabular(guv.cwd / "effectif.xlsx").contains("Org")



@path_dependency("test_xls_student_data")
def test_docs_flag(guv, xlsx):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    filename = "documents/flag"
    guv.create_file(filename, """\
Marco Bla
Pierre Blahblahfoo
Michel Barbarbar
Mathilde Barbarbar
""")

    guv.change_config(f"""
    DOCS.flag("{filename}", colname="Flag")
    """)

    guv().succeed()
    xlsx.tabular(guv.cwd / "effectif.xlsx").contains("Flag")


@path_dependency("test_xls_student_data")
def test_docs_apply_cell(guv, xlsx):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    guv.change_config("""
    DOCS.apply_cell("marco.bla@etu.utc.fr", "Tutorial", "D4")
    """)

    guv().succeed()


@path_dependency("test_xls_student_data")
def test_docs_switch(guv, xlsx):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)

    filename = "documents/swaps"
    guv.create_file(filename, """\
marco.bla@etu.utc.fr --- pierre.blahblahfoo@etu.utc.fr
michel.barbarbar@etu.utc.fr --- mathilde.barbarbar@etu.utc.fr
""")

    guv.change_config(f"""
    DOCS.switch("{filename}", colname="Tutorial")
    """)

    guv().succeed()
