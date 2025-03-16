import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_week_slots")
def test_html_inst(guv, guvcapfd):
    guv.cd(guv.semester, guv.uvs[0])
    guv("html_inst").succeed()
    assert (guv.cwd / "generated" / "intervenants.html").is_file()
    guvcapfd.stdout_search(".  html_inst")
    guvcapfd.no_warning()
