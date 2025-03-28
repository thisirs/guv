import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_csv_inscrits")
def test_xls_student_data_v1(guv, guvcapfd):
    """Aggrégation données étudiantes v1"""

    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("inscrits.raw", "documents")
    guv.copy_file("extraction_enseig_note.XLS", "documents")
    guv.copy_file("SY02 Notes.xlsx", "documents")

    guv.change_config(ENT_LISTING="documents/extraction_enseig_note.XLS")
    guv.change_config(AFFECTATION_LISTING="documents/inscrits.raw")
    guv.change_config(MOODLE_LISTING="documents/SY02 Notes.xlsx")

    guv("xls_student_data").succeed()
    guvcapfd.stdout_search(".  xls_student_data")
    guvcapfd.no_warning()
    guvcapfd.reset()
    assert (guv.cwd / "generated" / "student_data.xlsx").is_file()

    guv("xls_student_data_merge").succeed()
    guvcapfd.stdout_search(".  xls_student_data_merge")
    guvcapfd.no_warning()
    guvcapfd.reset()
    assert (guv.cwd / "effectif.xlsx").is_file()

    guv.change_config("""
    DOCS.apply_df(lambda df: df.assign(grade1=1))
    DOCS.apply_df(lambda df: df.assign(ects="A"))
    """)

    guv().succeed()
    guvcapfd.stdout_search(".  xls_student_data_merge")
    guvcapfd.no_warning()


@path_dependency("test_csv_inscrits", name="test_xls_student_data", cache=True)
def test_xls_student_data_v2(guv, guvcapfd):
    """Aggrégation données étudiantes v2"""

    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("inscrits.raw", "documents")
    guv.copy_file("ENT_v2.xls", "documents")
    guv.copy_file("SY02 Notes.xlsx", "documents")

    guv.change_config(ENT_LISTING="documents/ENT_v2.xls")
    guv.change_config(AFFECTATION_LISTING="documents/inscrits.raw")
    guv.change_config(MOODLE_LISTING="documents/SY02 Notes.xlsx")

    guv("xls_student_data").succeed()
    guvcapfd.stdout_search(".  xls_student_data")
    guvcapfd.no_warning()
    guvcapfd.reset()
    assert (guv.cwd / "generated" / "student_data.xlsx").is_file()

    guv("xls_student_data_merge").succeed()
    guvcapfd.stdout_search(".  xls_student_data_merge")
    guvcapfd.no_warning()
    guvcapfd.reset()
    assert (guv.cwd / "effectif.xlsx").is_file()

    guv.change_config("""
    DOCS.apply_df(lambda df: df.assign(grade1=1))
    DOCS.apply_df(lambda df: df.assign(ects="A"))
    """)

    guv().succeed()
    guvcapfd.stdout_search(".  xls_student_data_merge")
    guvcapfd.no_warning()

    guv.change_config("""\
    import numpy as np

    def add_groups(df):
        g = np.tile(["g1", "g2"], len(df))[: len(df)]
        np.random.shuffle(g)
        df = df.assign(group_1=g)

        g = np.repeat(["g3", "g4"], (len(df) // 2, len(df) // 2 + 1))[: len(df)]
        np.random.shuffle(g)
        df = df.assign(group_2=g)

        return df

    DOCS.apply_df(add_groups)
    """)
    guv().succeed()
