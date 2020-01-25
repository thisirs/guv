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
    check_columns
)
from .dodo_students import task_xls_student_data_merge
from .dodo_instructors import task_xls_affectation
from .scripts.xls_gradebook import run


@actionfailed_on_exception
def task_csv_for_upload():
    """Fichier csv de notes prêtes à être chargées sur l'ENT.

Crée un fichier csv de notes prêtes à être chargées sur l'ENT. La
colonne des notes est fixée par l'argument `grade_colname' et est
prise dans le fichier `student_data_merge.xlsx'. L'argument optionnel
`comment_colname' permet d'ajouter des commentaires.
    """

    @taskfailed_on_exception
    def csv_for_upload(csv_fname, xls_merge, grade_colname, comment_colname, ects):
        if grade_colname is None:
            return TaskFailed('Missing grade_colname')

        if ects and comment_colname:
            raise Exception("No comment column required when uploading ECTS")

        df = pd.read_excel(xls_merge)

        check_columns(df, grade_colname, file=xls_merge)

        cols = {
            'Nom': df.Nom,
            'Prénom': df['Prénom'],
            'Login': df.Login,
            'Note': df[grade_colname],
        }
        col_names = ['Nom', 'Prénom', 'Login', 'Note']

        if not ects:
            if comment_colname is None:
                col_names.append('Commentaire')
                cols['Commentaire'] = ""
            else:
                check_columns(df, comment_colname, file=xls_merge)
                col_names.append('Commentaire')
                cols['Commentaire'] = np.where(df[comment_colname].isnull(),
                                               np.nan,
                                               'Corrigé par ' + df[comment_colname])

        df0 = pd.DataFrame(cols, columns=col_names)
        df0 = df0[col_names]
        df0 = df0.sort_values(['Nom', 'Prénom'])

        with Output(csv_fname, protected=True) as csv_fname:
            df0.to_csv(csv_fname(), index=False, sep=';')

    args = parse_args(
        task_csv_for_upload,
        argument('-g', '--grade-colname', required=True),
        argument('--ects', action='store_true'),
        argument('-c', '--comment-colname', required=False)
    )

    planning, uv, info = get_unique_uv()
    csv_fname = generated(f'{args.grade_colname}_ENT.csv', **info)
    xls_merge = generated(task_xls_student_data_merge.target, **info)
    deps = [generated(task_xls_student_data_merge.target, **info)]
    return {
        'actions': [(csv_for_upload, [csv_fname, xls_merge, args.grade_colname, args.comment_colname, args.ects])],
        'targets': [csv_fname],
        'file_dep': deps
    }


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
        df = df.sort_values(['Nom', 'Prénom'])

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
        argument('-e', '--exam', required=True),
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
    data_file = generated(task_xls_student_data_merge.target, **info)
    docs = documents("", **info)
    deps = [data_file]
    return {
        'actions': [(xls_grades_sheet, [data_file, docs])],
        'file_dep': deps,
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
    xls_merge = generated(task_xls_student_data_merge.target, **info)
    yaml_fname = generated('QCM.yaml', **info)
    deps = [xls_merge]
    return {
        'actions': [(yaml_QCM, [yaml_fname, xls_merge])],
        'targets': [yaml_fname],
        'file_dep': deps,
    }


@actionfailed_on_exception
def task_xls_assignment_grade():
    """Création d'un fichier Excel pour remplissage des notes par les intervenants"""

    def xls_assignment_grade(inst_uv, xls_merge, target):
        inst_uv = pd.read_excel(inst_uv)
        TD = inst_uv['Lib. créneau'].str.contains('^D')
        inst_uv_TD = inst_uv.loc[TD]
        insts = inst_uv_TD['Intervenants'].unique()

        df = pd.read_excel(xls_merge)
        df = df[['Nom', 'Prénom', 'Courriel']].sort_values(['Nom', 'Prénom'])
        df = df.assign(Note=np.nan)

        with Output(target) as target:
            writer = pd.ExcelWriter(target())
            for inst in insts:
                df.to_excel(writer, sheet_name=inst, index=False)
            writer.save()

    args = parse_args(
        task_xls_assignment_grade,
        argument('-e', '--exam', required=True),
    )

    planning, uv, info = get_unique_uv()
    xls_merge = generated(task_xls_student_data_merge.target, **info)
    inst_uv = documents(task_xls_affectation.target, **info)
    target = generated(f'{args.exam}.xlsx', **info)

    return {
        'actions': [(xls_assignment_grade, [inst_uv, xls_merge, target])],
        'file_dep': [xls_merge, inst_uv],
        'targets': [target],
    }
