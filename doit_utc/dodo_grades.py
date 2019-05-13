import os
import sys
import numpy as np
import pandas as pd
import oyaml as yaml            # Ordered yaml

from doit import get_var

from .utils import (
    Output,
    documents,
    generated,
    selected_uv,
    action_msg,
)
from .dodo_students import task_xls_student_data_merge
from .dodo_instructors import task_xls_affectation
from .scripts.xls_gradebook import run


def task_csv_for_upload():
    """Fichier csv de notes prêtes à être chargées sur l'ENT.

Prend les informations dans le fichier
'generated/{planning}_{uv}_student_data_merge.xlsx' grâce aux
variables fournies en arguments: PLANNING, UV, GRADE_COLNAME,
COMMENT_COLNAME.
    """

    def csv_for_upload(csv_fname, xls_merge, grade_colname, comment_colname):
        if grade_colname is None:
            raise Exception('Missing grade_colname')

        df = pd.read_excel(xls_merge)
        cols = {
            'Nom': df.Nom,
            'Prénom': df['Prénom'],
            'Login': df.Login,
            'Note': df[grade_colname],
        }
        col_names = ['Nom', 'Prénom', 'Login', 'Note']
        if comment_colname is not None:
            col_names.append('Commentaire')
            cols['Commentaire'] = np.where(df[comment_colname].isnull(),
                                           np.nan,
                                           'Corrigé par ' + df[comment_colname])

        df0 = pd.DataFrame(cols, columns=col_names)
        df0 = df0[col_names]
        df0 = df0.sort_values(['Nom', 'Prénom'])

        with Output(csv_fname) as csv_fname:
            df0.to_csv(csv_fname(), index=False, sep=';')

    uvs = list(selected_uv())
    if len(uvs) == 1:
        grade_colname = get_var('grade_colname')
        comment_colname = get_var('comment_colname')
        if grade_colname:
            planning, uv, info = uvs[0]
            csv_fname = generated(f'{grade_colname}_ENT.csv', **info)
            xls_merge = generated(task_xls_student_data_merge.target, **info)
            deps = [generated(task_xls_student_data_merge.target, **info)]
            return {
                'actions': [(csv_for_upload, [csv_fname, xls_merge, grade_colname, comment_colname])],
                'targets': [csv_fname],
                'file_dep': deps
            }
        else:
            return action_msg("Il faut spécifier le nom de la colonne")
    else:
        return action_msg("Une seule UV doit être sélectionnée")


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

    uvs = list(selected_uv())
    if len(uvs) == 1:
        pl, uv, info = uvs[0]
        exam = get_var('exam')
        if exam:
            xls_sheets = documents(f'{exam}.xlsx', **info)
            xls_grades = documents(f'{exam}_notes.xlsx', **info)

            return {
                'actions': [(xls_merge_final_grade, [xls_sheets, xls_grades])],
                'targets': [xls_grades],
                'file_dep': [xls_sheets],
                'verbosity': 2
            }
        else:
            return action_msg("Il faut spécifier le nom de l'examen")
    else:
        return action_msg("Une seule UV doit être sélectionnée")


def task_xls_grades_sheet():
    """Génère un fichier Excel pour faciliter la correction des examens/projets/jury"""

    uvs = list(selected_uv())
    if len(uvs) == 1:
        pl, uv, info = uvs[0]
        data_file = generated(task_xls_student_data_merge.target, **info)
        cmd_args = sys.argv[2:] + ['-o', f'{uv}/documents/', '-d', data_file]

        return {
            'actions': [(run, [cmd_args])],
            'file_dep': [data_file] if data_file else [],
            'params': ([{'name': arg,
                         'long': arg,
                         'default': 'dummy'} for arg in ['type', 'name', 'uv', 'planning', 'data', 'output-file', 'struct', 'group', 'config', 'insts']] +
                       [{'name': arg,
                         'short': arg,
                         'default': 'dummy'} for arg in ['d', 'o', 's', 'g', 'c', 'i']] +
                       [{'name': arg,
                         'short': arg,
                         'type': bool,
                         'default': 'dummy'} for arg in ['h']]),
            'verbosity': 2,
            'uptodate': [False]
        }
    else:
        return action_msg("Une seule UV doit être sélectionnée")


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

    uvs = list(selected_uv())
    if len(uvs) == 1:
        planning, uv, info = uvs[0]
        xls_merge = generated(task_xls_student_data_merge.target, **info)
        yaml_fname = generated('QCM.yaml', **info)
        return {
            'actions': [(yaml_QCM, [yaml_fname, xls_merge])],
            'targets': [yaml_fname],
            'file_dep': [xls_merge],
            'verbosity': 2
        }
    else:
        return action_msg("Une seule UV doit être sélectionnée")


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

    uvs = list(selected_uv())
    if len(uvs) == 1:
        exam = get_var('exam')
        if exam:
            planning, uv, info = uvs[0]
            xls_merge = generated(task_xls_student_data_merge.target, **info)
            inst_uv = documents(task_xls_affectation.target, **info)
            target = generated(f'{exam}.xlsx', **info)
            return {
                'file_dep': [xls_merge, inst_uv],
                'targets': [target],
                'actions': [(xls_assignment_grade, [inst_uv, xls_merge, target])],
                'verbosity': 2
            }
        else:
            return action_msg("Il faut spécifier le nom de l'examen")
    else:
        return action_msg("Une seule UV doit être sélectionnée")
