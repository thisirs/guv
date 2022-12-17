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
from ..utils import argument, sort_values
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
            help="Modèle permettant de formatter plus précisément le commentaire. Le mot-clé ``msg`` représente la donnée présente dans la colonne ``--comment-colname``. Par défaut, on a ``{msg}``.",
        ),
    )

    def setup(self):
        super().setup()

        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target = self.build_target()

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

        Il faut grader l'encodage par défault (latin-1).
        """))


class XlsMergeFinalGrade(UVTask, CliArgsMixin):
    """Fichier Excel des notes finales attribuées

    Transforme un classeur Excel avec une feuille par correcteur en une
    seule feuille où les notes sont concaténées pour fusion/révision
    manuelle.
    """

    target_dir = "documents"
    target_name = "{exam}_notes.xlsx"
    cli_args = (argument("-e", "--exam", required=True, help="Nom de l'examen"),)
    unique_uv = True

    def setup(self):
        super().setup()
        self.parse_args()

        self.xls_sheets = os.path.join(self.settings.SEMESTER_DIR, self.target_dir, f"{self.exam}.xlsx")
        self.file_dep = [self.xls_sheets]
        self.target = self.build_target()

    def run(self):
        xls = pd.ExcelFile(self.xls_sheets)
        dfall = xls.parse(xls.sheet_names[0])
        dfall = dfall[["Nom", "Prénom", "Courriel"]]

        dfs = []
        for sheet in xls.sheet_names:
            df = xls.parse(sheet)
            df = df.loc[~df.Note.isnull()]
            df["Correcteur"] = sheet
            dfs.append(df)

        # Concaténation de tous les devoirs qui ont une note
        df = pd.concat(dfs, axis=0)

        # On rattrape les absents
        df = pd.merge(dfall, df, how="left", on=["Nom", "Prénom", "Courriel"])
        df = sort_values(df, ["Nom", "Prénom"])

        csv_grades = os.path.splitext(self.target)[0] + ".csv"
        with Output(csv_grades, protected=True) as out:
            df.to_csv(out.target, index=False)

        with Output(self.target, protected=True) as out:
            df.to_excel(out.target, index=False)


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


class XlsAssignmentGrade(UVTask, CliArgsMixin):
    """Création d'un fichier Excel pour remplissage des notes par les intervenants"""

    target_dir = "generated"
    target_name = "{exam}.xlsx"
    cli_args = (argument("-e", "--exam", required=True, help="Nom de l'examen"),)
    uptodate = True

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.week_slots = WeekSlots.target_from(**self.info)
        self.file_dep = [self.week_slots, self.xls_merge]

        self.parse_args()
        self.target = self.build_target()

    def run(self):
        week_slots = WeekSlots.read_target(self.week_slots)
        TD = week_slots['Lib. créneau'].str.contains('^D')
        week_slots_TD = week_slots.loc[TD]
        insts = week_slots_TD['Intervenants'].unique()

        df = XlsStudentDataMerge.read_target(self.xls_merge)
        df = df[['Nom', 'Prénom', 'Courriel']]
        df = sort_values(df, ['Nom', 'Prénom'])
        df = df.assign(Note=np.nan)

        with Output(self.target, protected=True) as out:
            writer = pd.ExcelWriter(out.target)
            for inst in insts:
                df.to_excel(writer, sheet_name=inst, index=False)
            writer.save()
