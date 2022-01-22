from pathlib import Path
import pytest


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_pdf_attendance(semester_dir):
    """Test PdfAttendance"""

    semester_dir.change_relative_cwd("A2020", "SY02")
    ret = semester_dir.run_cli(
        "pdf_attendance",
        "-t",
        "foo",
        "-g",
        "TD",
        "--save-tex"
    )
    assert ret == 0
    semester_dir.assert_out_search(
        ".  pdf_attendance",
        "Écriture du fichier `generated/attendance_TD.zip`"
    )
    assert Path(semester_dir.cwd, "generated", "attendance_TD.zip").is_file()


@pytest.mark.use_tree.with_args("test_xls_student_data")
def test_pdf_attendance_full(semester_dir):
    """Test PdfAttendanceFull"""

    semester_dir.change_relative_cwd("A2020", "SY02")
    ret = semester_dir.run_cli(
        "pdf_attendance_full",
        "-g",
        "TD",
        "-n",
        "14",
        "--save-tex"
    )
    assert ret == 0
    semester_dir.assert_out_search(
        ".  pdf_attendance_full",
        "Écriture du fichier `generated/attendance_TD_full.zip`"
    )
    assert Path(semester_dir.cwd, "generated", "attendance_TD_full.zip").is_file()
