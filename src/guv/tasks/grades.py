"""
Ce module rassemble les tâches liées aux notes : chargement de notes
numériques ou ECTS sur l'ENT.
"""

import os

import numpy as np
import oyaml as yaml  # Ordered yaml
import pandas as pd
import textwrap

from ..logger import logger
from ..utils import argument, sort_values, normalize_string
from ..utils_config import Output, check_if_present
from .base import CliArgsMixin, UVTask
from .instructors import WeekSlots
from .students import XlsStudentDataMerge


class CsvForUpload(UVTask, CliArgsMixin):
    """Fichier csv de notes prêtes à être chargées sur l'ENT.

    Crée un fichier csv nommé ``{grade_colname}_ENT.csv`` de notes
    prêtes à être chargées sur l'ENT. La colonne des notes est fixée
    par l'argument ``--grade_colname`` et est prise dans le fichier
    ``effectif.xlsx``. L'argument optionnel ``--comment_colname``
    permet d'ajouter des commentaires éventuellement formaté avec
    l'option ``--format``.

    {options}

    Examples
    --------

    - Fichier de notes ECTS d'après la colonne ``Note ECTS`` :

      .. code:: bash

         guv csv_for_upload --grade-colname "Note ECTS" --ects

    - Fichier de notes avec commentaire associé d'après la colonne
      ``Correcteur`` :

      .. code:: bash

         guv csv_for_upload --grade-colname Note_TP --comment-colname "Correcteur" --format "Corrigé par {msg}"

    """

    uptodate = False
    target_dir = "generated"
    target_name = "{grade_colname}_ENT.csv"
    cli_args = (
        argument(
            "-g",
            "--grade-colname",
            required=True,
            help="Nom de la colonne contenant la note à exporter.",
        ),
        argument(
            "--ects",
            action="store_true",
            help="Précise si la note à exporter est une note ECTS. D'après l'ENT, il ne faut alors pas de colonne de commentaires et la note n'est pas arrondie (l'ENT n'aime pas quand il y a trop de décimales).",
        ),
        argument(
            "-c",
            "--comment-colname",
            required=False,
            help="Nom de la colonne contenant un commentaire à ajouter dans le fichier exporté.",
        ),
        argument(
            "-f",
            "--format",
            required=False,
            default="{msg}",
            help="Modèle permettant de formatter plus précisément le commentaire. Le mot-clé ``msg`` représente la donnée présente dans la colonne ``--comment-colname``. Par défaut, on a ``%(default)s``.",
        ),
    )

    def setup(self):
        super().setup()

        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target = self.build_target(grade_colname=normalize_string(self.grade_colname, type="file"))

    def run(self):
        if self.ects and self.comment_colname:
            raise Exception("No comment column required when uploading ECTS")

        df = XlsStudentDataMerge.read_target(self.xls_merge)

        check_if_present(
            df, self.grade_colname, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
        )

        cols = {
            "Nom": df.Nom,
            "Prénom": df["Prénom"],
            "Login": df.Login,
            "Note": df[self.grade_colname],
        }
        col_names = ["Nom", "Prénom", "Login", "Note"]

        if self.ects:
            warn = False
            ects_grades = ["ABSENT", "RESERVE", "EQUIVALENCE", "A", "B", "C", "D", "E", "FX", "F"]
            for index, row in df.iterrows():
                if row[self.grade_colname] not in ects_grades:
                    warn = True
                    logger.warning(f'Note non reconnue pour l\'étudiant `{row["Nom"]} {row["Prénom"]}` : `{row[self.grade_colname]}`')

            if warn:
                msg = ", ".join(f"`{e}`" for e in ects_grades)
                logger.warning(f"Les notes ECTS autorisées sont {msg} ")
        else:
            # La note doit être arrondie sinon l'ENT grogne (champ
            # trop long)
            def round_grade(e):
                try:
                    return round(pd.to_numeric(e), 2)
                except Exception:
                    return e

            cols["Note"] = cols["Note"].apply(round_grade)

            # Ajout d'une colonne de commentaire par copie
            if self.comment_colname is None:
                col_names.append("Commentaire")
                cols["Commentaire"] = ""
            else:
                check_if_present(
                    df, self.comment_colname, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
                )
                col_names.append("Commentaire")

                def format_msg(e):
                    if pd.isna(e):
                        return np.nan
                    else:
                        return self.format.format(msg=e)

                cols["Commentaire"] = df[self.comment_colname].apply(format_msg)

        df0 = pd.DataFrame(cols, columns=col_names)
        df0 = df0[col_names]
        df0 = sort_values(df0, ["Nom", "Prénom"])

        with Output(self.target, protected=True) as out:
            df0.to_csv(out.target, index=False, sep=";", encoding="latin-1")

        logger.info(textwrap.dedent("""\
        À charger sur :
        - https://webapplis.utc.fr/smeappli/resultats_intermediaires/
        - https://webapplis.utc.fr/smeappli/resultats_finaux/

        Il faut garder l'encodage par défaut (latin-1).
        """))


class YamlQCM(UVTask):
    """Génère un fichier yaml prérempli pour noter un QCM"""

    target_dir = "generated"
    target_name = "QCM.yaml"

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.target = self.build_target()
        self.file_dep = [self.xls_merge]

    def run(self):
        df = XlsStudentDataMerge.read_target(self.xls_merge)
        dff = df[["Nom", "Prénom", "Courriel"]]
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


class CsvAmcList(UVTask):
    """Crée un fichier csv à réutiliser directement dans AMC"""

    target_dir = "generated"
    target_name = "AMC_student_list.csv"
    uptodate = False

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.target = self.build_target()

    def run(self):
        df = pd.read_excel(self.xls_merge, engine="openpyxl")
        dff = df[["Login", "Courriel"]]
        dff = dff.assign(**{"Name": df["Nom"].astype(str) + " " + df["Prénom"].astype(str)})

        with Output(self.target) as out:
            dff.to_csv(out.target, index=False)
