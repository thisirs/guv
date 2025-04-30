import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_utc_uv_list_to_csv")
def test_xls_student_data_v1(guv, guvcapfd):
    """Agrégation données étudiantes v1"""

    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("inscrits.raw", "documents")
    guv.copy_file("extraction_enseig_note.XLS", "documents")
    guv.copy_file("SY02 Notes.xlsx", "documents")

    guv.change_config("""\
    from guv.tasks.internal import Documents
    DOCS = Documents()
    DOCS.add_utc_ent_listing("documents/extraction_enseig_note.XLS")
    DOCS.add_affectation("documents/inscrits.raw")
    DOCS.add_moodle_listing("documents/SY02 Notes.xlsx")
    """)

    guv("xls_student_data").succeed()
    guvcapfd.stdout_search(".  xls_student_data")
    guvcapfd.no_warning()
    guvcapfd.reset()
    assert (guv.cwd / "generated" / "student_data_final.csv").is_file()
    assert (guv.cwd / "effectif.xlsx").is_file()

    guv.change_config("""
    DOCS.apply_df(lambda df: df.assign(grade1=1))
    DOCS.apply_df(lambda df: df.assign(ects="A"))
    """)

    guv().succeed()
    guvcapfd.stdout_search(".  xls_student_data")
    guvcapfd.no_warning()


@path_dependency("test_utc_uv_list_to_csv", name="test_xls_student_data", cache=True)
def test_xls_student_data_v2(guv, guvcapfd):
    """Aggrégation données étudiantes v2"""

    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("inscrits.raw", "documents")
    guv.copy_file("ENT_v2.xls", "documents")
    guv.copy_file("SY02 Notes.xlsx", "documents")

    guv.change_config("""\
    from guv.tasks.internal import Documents
    DOCS = Documents()
    DOCS.add_utc_ent_listing("documents/ENT_v2.xls")
    DOCS.add_affectation("documents/inscrits.raw")
    DOCS.add_moodle_listing("documents/SY02 Notes.xlsx")
    """)

    guv("xls_student_data").succeed()
    guvcapfd.stdout_search(".  xls_student_data")
    guvcapfd.no_warning()
    guvcapfd.reset()
    assert (guv.cwd / "generated" / "student_data_final.csv").is_file()
    assert (guv.cwd / "effectif.xlsx").is_file()

    guv.change_config("""
    DOCS.apply_df(lambda df: df.assign(grade1=1))
    DOCS.apply_df(lambda df: df.assign(ects="A"))
    """)

    guv().succeed()
    guvcapfd.stdout_search(".  xls_student_data")
    guvcapfd.no_warning()
    guvcapfd.reset()

    guv.change_config("""\
    import numpy as np

    def add_groups(df):
        g = np.tile(["g1", "g2"], len(df))[: len(df)]
        np.random.shuffle(g)
        df = df.assign(group_1=g)

        g = np.repeat(["g1", "g2", "g3", "g4"], len(df) // 4 + 1)[: len(df)]
        np.random.shuffle(g)
        df = df.assign(group_2=g)

        return df

    DOCS.apply_df(add_groups)
    """)
    guv().succeed()
    guvcapfd.stdout_search(".  xls_student_data")
    guvcapfd.no_warning()
