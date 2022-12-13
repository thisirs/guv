import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_planning_slots")
class TestCalInst:
    def test_cal_inst0(self, guv, guvcapfd):
        guv.cd(guv.semester)
        guv("cal_inst").failed()
        guvcapfd.stdout_search("La variable 'DEFAULT_INSTRUCTOR' est incorrecte")

    def test_cal_inst1(self, guv, guvcapfd):
        guv.change_config(DEFAULT_INSTRUCTOR="Bob Marley")
        guv("cal_inst")
        guvcapfd.stdout_search("0 créneau pour `Bob Marley`")

    def test_cal_inst2(self, guv, xlsx, guvcapfd):
        uv = guv.uvs[0]
        inst = f"Inst_{uv}_0"

        guv.change_config(DEFAULT_INSTRUCTOR=inst)

        guv("cal_inst").succeed()
        guvcapfd.stdout_search(f"du fichier `generated/{inst}_{guv.semester}_calendrier.pdf`")

    def test_cal_inst3(self, guv, xlsx, guvcapfd):
        uv = guv.uvs[0]
        inst = f"Inst_{uv}_0"

        guv(f"cal_inst -i {inst}").succeed()
        guvcapfd.stdout_search(f"du fichier `generated/{inst}_{guv.semester}_calendrier.pdf`")
