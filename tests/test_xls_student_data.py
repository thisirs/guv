import pytest
from pytest_path_dependency import path_dependency

@path_dependency("test_createsemester")
def test_cls_studente_data_no_documents_semester(guv):
    guv.cd(guv.semester)
    guv().succeed()


@path_dependency("test_createsemester")
def test_cls_studente_data_no_documents_uv(guv):
    for uv in guv.uvs:
        guv.cd(guv.semester, uv)
        guv().succeed()


@path_dependency("test_createsemester", cache=True)
def test_xls_student_data(guv, xlsx, guvcapfd):
    uv = guv.uvs[0]
    guv.cd(guv.semester, uv)
    guv.copy_file("base_listing.xlsx", "documents")
    guv.copy_file("SY02 Notes.xlsx", "documents")

    guv.change_config("""\
    from guv.tasks.internal import Documents
    DOCS = Documents()
    DOCS.add("documents/base_listing.xlsx")
    """)
    guv().succeed()
    guvcapfd.stdout_search(".  xls_student_data")
    guvcapfd.no_warning()
    guvcapfd.reset()
    guv.check_output_file(guv.cwd / "generated" / "student_data_final.csv")
    guv.check_output_file(guv.cwd / "effectif.xlsx")

    doc = xlsx.tabular(guv.cwd / "effectif.xlsx")
    doc.check_columns(
        "First name",
        "Last name",
        "Email",
        "Lecture",
        "Tutorial",
        "Practical work",
        "Login"
    )

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
        df = df.assign(group_1=g)

        g = np.repeat(["g1", "g2", "g3", "g4"], len(df) // 4)[: len(df)]
        df = df.assign(group_2=g)

        return df

    DOCS.apply_df(add_groups)
    """)
    guv().succeed()
    guvcapfd.stdout_search(".  xls_student_data")
    guvcapfd.no_warning()

