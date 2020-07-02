"""
Fichier qui regroupe des tâches liées aux notes: chargement de notes
numériques ou ECTS sur l'ENT, fichier Excel avec barème, fichier Excel
pour faire un jury.
"""

import os
import sys
import numpy as np
import pandas as pd
import oyaml as yaml            # Ordered yaml

from doit.exceptions import TaskFailed

from .utils import (
    Output,
    documents,
    generated,
    taskfailed_on_exception,
    actionfailed_on_exception,
    get_unique_uv,
    parse_args,
    argument,
    check_columns,
    sort_values
)
from .tasks import CliArgsMixin, UVTask
from .dodo_students import XlsStudentDataMerge
from .dodo_instructors import task_xls_affectation
from .gradebook import run


class CsvForUpload(CliArgsMixin, UVTask):
    """Fichier csv de notes prêtes à être chargées sur l'ENT.

Crée un fichier csv de notes prêtes à être chargées sur l'ENT. La
colonne des notes est fixée par l'argument `grade_colname' et est
prise dans le fichier `student_data_merge.xlsx'. L'argument optionnel
`comment_colname' permet d'ajouter des commentaires.
    """

    always_make = True
    cli_args = (
        argument(
            "-g",
            "--grade-colname",
            required=True,
            help="Nom de la colonne contenant la note à exporter",
        ),
        argument(
            "--ects",
            action="store_true",
            help="Précise si la note est une note ECTS (pas de commentaire)",
        ),
        argument(
            "-c",
            "--comment-colname",
            required=False,
            help="Nom de la colonne contenant un commentaire",
        ),
        argument(
            "-f",
            "--format",
            required=False,
            default="{msg}",
            help="Format pour créer un message dans le colonne commentaire",
        ),
    )

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)

        self.csv_fname = generated(f"{self.grade_colname}_ENT.csv", **self.info)
        self.xls_merge = generated(XlsStudentDataMerge.target, **self.info)

        self.targets = [self.csv_fname]
        self.file_dep = [self.xls_merge]

    def run(self):
        if self.grade_colname is None:
            return TaskFailed("Missing grade_colname")

        if self.ects and self.comment_colname:
            raise Exception("No comment column required when uploading ECTS")

        df = pd.read_excel(self.xls_merge)

        check_columns(df, self.grade_colname, file=self.xls_merge)

        cols = {
            "Nom": df.Nom,
            "Prénom": df["Prénom"],
            "Login": df.Login,
            "Note": df[self.grade_colname],
        }
        col_names = ["Nom", "Prénom", "Login", "Note"]

        if not self.ects:
            # La note doit être arrondie sinon l'ENT grogne (champ
            # trop long)
            def round_grade(e):
                try:
                    return round(pd.to_numeric(e), 2)
                except Exception:
                    return e

            cols["Note"] = cols["Note"].apply(round_grade)

            # Ajout d'un colonne de commentaire par copie
            if self.comment_colname is None:
                col_names.append("Commentaire")
                cols["Commentaire"] = ""
            else:
                check_columns(df, self.comment_colname, file=self.xls_merge)
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

        with Output(self.csv_fname, protected=True) as csv_fname:
            df0.to_csv(csv_fname(), index=False, sep=";")


@actionfailed_on_exception
def task_xls_merge_final_grade():
    """Fichier Excel des notes finales attribuées

Transforme un classeur Excel avec une feuille par correcteur en une
seule feuille où les notes sont concaténées pour fusion/révision
manuelle."""

    def xls_merge_final_grade(xls_sheets, xls_grades):
        xls = pd.ExcelFile(xls_sheets)
        dfall = xls.parse(xls.sheet_names[0])
        dfall = dfall[['Nom', 'Prénom', 'Courriel']]

        dfs = []
        for sheet in xls.sheet_names:
            df = xls.parse(sheet)
            df = df.loc[~df.Note.isnull()]
            df['Correcteur médian'] = sheet
            dfs.append(df)

        # Concaténation de tous les devoirs qui ont une note
        df = pd.concat(dfs, axis=0)

        # On rattrape les absents
        df = pd.merge(dfall, df, how='left', on=['Nom', 'Prénom', 'Courriel'])
        df = sort_values(df, ["Nom", "Prénom"])

        csv_grades = os.path.splitext(xls_grades)[0] + '.csv'
        with Output(csv_grades, protected=True) as csv_grades:
            df.to_csv(csv_grades(), index=False)

        with Output(xls_grades, protected=True) as xls_grades:
            df.to_excel(xls_grades(), index=False)

        # def max_grade(group):
        #     return group.loc[df['Note'].idxmax()]

        # dff = df.groupby(['Nom', 'Prénom'], group_keys=False).apply(max_grade)
        # dff.to_excel(xls_grades, index=False)

    args = parse_args(
        task_xls_merge_final_grade,
        argument('-e', '--exam', required=True, help="Nom de l'examen"),
    )

    planning, uv, info = get_unique_uv()
    xls_sheets = documents(f'{args.exam}.xlsx', **info)
    xls_grades = documents(f'{args.exam}_notes.xlsx', **info)
    deps = [xls_sheets]
    return {
        'actions': [(xls_merge_final_grade, [xls_sheets, xls_grades])],
        'targets': [xls_grades],
        'file_dep': deps,
    }


@actionfailed_on_exception
def task_xls_grades_sheet():
    """Génère un fichier Excel pour faciliter la correction des examens/projets/jury"""

    @taskfailed_on_exception
    def xls_grades_sheet(data_file, docs):
        cmd_args = sys.argv[2:] + ['-o', docs, '-d', data_file]
        run(cmd_args,
            prog="doit_utc xls_grades_sheet",
            description=task_xls_grades_sheet.__doc__)

    planning, uv, info = get_unique_uv()
    data_file = generated(XlsStudentDataMerge.target, **info)
    docs = documents("", **info)
    deps = [data_file]
    return {
        'actions': [(xls_grades_sheet, [data_file, docs])],
        'file_dep': deps,
        'uptodate': [False]
    }


@actionfailed_on_exception
def task_yaml_QCM():
    """Génère un fichier yaml prérempli pour noter un QCM"""

    def yaml_QCM(yaml_fname, xls_merge):
        df = pd.read_excel(xls_merge)
        dff = df[['Nom', 'Prénom', 'Courriel']]
        d = dff.to_dict(orient='index')
        rec = [{'Nom': record['Nom'] + ' ' + record['Prénom'],
                'Courriel': record['Courriel'],
                'Resultat': ''} for record in d.values()]

        rec = {'Students': rec, 'Answers': ''}

        with Output(yaml_fname, protected=True) as yaml_fname:
            with open(yaml_fname(), 'w') as fd:
                yaml.dump(rec, fd, default_flow_style=False)

    planning, uv, info = get_unique_uv()
    xls_merge = generated(XlsStudentDataMerge.target, **info)
    yaml_fname = generated('QCM.yaml', **info)
    deps = [xls_merge]
    return {
        'actions': [(yaml_QCM, [yaml_fname, xls_merge])],
        'targets': [yaml_fname],
        'file_dep': deps,
    }


class XlsAssignmentGrade(CliArgsMixin, UVTask):
    """Création d'un fichier Excel pour remplissage des notes par les intervenants"""

    cli_args = (argument("-e", "--exam", required=True, help="Nom de l'examen"),)
    always_make = True

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.xls_merge = generated(XlsStudentDataMerge.target, **self.info)
        self.inst_uv = documents(task_xls_affectation.target, **self.info)
        self.target = generated(f'{self.exam}.xlsx', **self.info)
        self.file_dep = [self.inst_uv, self.xls_merge]

    def run(self):
        inst_uv = pd.read_excel(self.inst_uv)
        TD = inst_uv['Lib. créneau'].str.contains('^D')
        inst_uv_TD = inst_uv.loc[TD]
        insts = inst_uv_TD['Intervenants'].unique()

        df = pd.read_excel(self.xls_merge)
        df = df[['Nom', 'Prénom', 'Courriel']]
        df = sort_values(df, ['Nom', 'Prénom'])
        df = df.assign(Note=np.nan)

        with Output(self.target, protected=True) as target:
            writer = pd.ExcelWriter(target())
            for inst in insts:
                df.to_excel(writer, sheet_name=inst, index=False)
            writer.save()
