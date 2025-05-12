"""
Ce module rassemble les tâches liées aux notes : chargement de notes
numériques ou ECTS sur l'ENT.
"""

import oyaml as yaml  # Ordered yaml

from ..utils_config import Output
from .base import UVTask
from .internal import XlsStudentData


class YamlQCM(UVTask):
    """Génère un fichier yaml prérempli pour noter un QCM"""

    target_dir = "generated"
    target_name = "QCM.yaml"

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentData.target_from(**self.info)
        self.target = self.build_target()
        self.file_dep = [self.xls_merge]

    def run(self):
        df = XlsStudentData.read_target(self.xls_merge)
        columns = [self.settings[e] for e in ["LASTNAME_COLUMN", "NAME_COLUMN", "EMAIL"]]
        dff = df[columns]
        d = dff.to_dict(orient="index")
        rec = [
            {
                "Nom": record["Nom"] + " " + record["Prénom"],
                "Courriel": record["Courriel"],
                "Resultat": "",
            }
            for record in d.values()
        ]

        rec = {"Students": rec, "Answers": ""}

        with Output(self.target, protected=True) as out:
            with open(out.target, "w") as fd:
                yaml.dump(rec, fd, default_flow_style=False)
