import pytest
from tests.plugins.test_path import path_dependency


@path_dependency("test_planning_slots")
class TestCalInst:
    def test_cal_inst0(self, guv, guvcapfd):
        guv.cd(guv.semester)
        guv("cal_inst").failed()
        guvcapfd.stdout_search("La variable 'DEFAULT_INSTRUCTOR' est incorrecte")
        guvcapfd.no_warning()

    def test_cal_inst1(self, guv, guvcapfd):
        uv = guv.uvs[0]
        inst = f"Inst {uv} A"

        guv.change_config(DEFAULT_INSTRUCTOR="Bob Marley")
        guv("cal_inst")
        guvcapfd.stdout_search("0 créneau pour `Bob Marley`")
        guvcapfd.reset()

        guv.change_config(DEFAULT_INSTRUCTOR=inst)
        guv("cal_inst")
        guvcapfd.stdout_search(f"1 créneau pour `{inst}`")
        guvcapfd.no_warning()


    def test_cal_inst2(self, guv, xlsx, guvcapfd):
        uv = guv.uvs[0]
        inst = f"Inst {uv} A"
        inst_alt = f"Inst_{uv}_A"

        guv.change_config(DEFAULT_INSTRUCTOR=inst)

        guv("cal_inst").succeed()
        guvcapfd.stdout_search(f"du fichier `generated/{inst_alt}_{guv.semester}_calendrier.pdf`")
        guvcapfd.no_warning()

    def test_cal_inst3(self, guv, xlsx, guvcapfd):
        uv = guv.uvs[0]
        inst = f"Inst {uv} A"
        inst_alt = f"Inst_{uv}_A"

        guv(f'cal_inst -i "{inst}"').succeed()
        guvcapfd.stdout_search(f"du fichier `generated/{inst_alt}_{guv.semester}_calendrier.pdf`")
        guvcapfd.no_warning()
