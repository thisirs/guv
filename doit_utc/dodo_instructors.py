"""
Fichier qui regroupe des tâches de gestion des intervenants au sein
d'une UV : fichier Excel du nombre d'heures théoriques, décompte des
heures remplacées.
"""

import os
import re
import pandas as pd
from pandas.api.types import CategoricalDtype

from doit.exceptions import TaskFailed

from .dodo_utc import UtcUvListToCsv
from .utils_config import Output, documents, generated, selected_uv, semester_settings
from .utils import add_templates, lib_list
from .tasks import UVTask, TaskBase
from .scripts.excel_hours import create_excel_file


def create_insts_list(df):
    "Agrège les données d'affectation des Cours/TD/TP"

    def course_list(e):
        "Return course list like C1, D2, T1A"
        return ', '.join(sorted(e, key=lib_list))

    def score(libs):
        "Renvoie un tuple comptant les types de cours Cours/TD/TP"
        sc = [0, 0, 0]
        mapping = {'C': 0, 'D': 1, 'T': 2}
        for lib in libs:
            m = re.search('([CDT])[0-9]*([AB]?)', lib)
            if m:
                ix = mapping[m.group(1)]
                if m.group(2):
                    sc[ix] += .5
                else:
                    sc[ix] += 1
            else:
                raise Exception(f"L'identifiant {lib} n'est pas matché")
        return tuple(sc)

    def myapply(df):
        e = df['Lib. créneau'] + df['Semaine'].fillna('')
        resp = int(df['Responsable'].sum())
        s = score(e)
        return pd.Series({
            'CourseList': course_list(e),
            'SortCourseList': s,
            'Cours': s[0],
            'TD': s[1],
            'TP': s[2],
            'Responsable': resp
        })

    df = df.groupby('Intervenants')
    df = df.apply(myapply)
    df = df.reset_index()

    return(df)


@add_templates(target='intervenants.xlsx')
def task_xls_instructors():
    """Fichier de détails global des intervenants toutes UV confondues"""

    doc = documents(task_xls_instructors.target)

    def xls_instructors(doc):
        if not os.path.exists(doc):
            return TaskFailed(f"Pas de fichier `{doc}'")

    return {
        'actions': [(xls_instructors, [doc])],
        'targets': [doc]
    }


class AddInstructors(TaskBase):
    """Ajoute les intervenants dans la liste csv des créneaux"""

    target = "UTC_UV_list_instructors.csv"

    def __init__(self):
        self.target = generated(AddInstructors.target)
        self.uv_list = documents(UtcUvListToCsv.target)
        self.affectations = [
            (uv, XlsAffectation.build_target(planning, uv, info))
            for planning, uv, info in selected_uv()
        ]
        files = [f for _, f in self.affectations]
        self.file_dep = files + [self.uv_list]

    def run(self):
        df_csv = pd.read_csv(self.uv_list)

        df_affs = [
            pd.read_excel(xls_aff).assign(**{"Code enseig.": uv})
            for uv, xls_aff in self.affectations
        ]

        df_aff = pd.concat(df_affs, ignore_index=True)
        df_aff.Semaine = df_aff.Semaine.astype(object)

        df_merge = pd.merge(
            df_csv,
            df_aff,
            how="left",
            on=[
                "Code enseig.",
                "Jour",
                "Heure début",
                "Heure fin",
                "Semaine",
                "Lib. créneau",
                "Locaux",
            ],
        )

        with Output(self.target) as target:
            df_merge.to_csv(target(), index=False)


def read_xls_details(fn):
    """Lit un fichier Excel avec un ordre sur la colonne 'Statut'."""

    sts = ["MCF", "PR", "PRAG", "PRCE", "PAST", "ECC", "Doct", "ATER", "Vacataire"]
    status_type = CategoricalDtype(categories=sts, ordered=True)

    return pd.read_excel(fn, dtype={
        'Statut': status_type
    })


@add_templates(target='intervenants_details.xlsx')
def task_xls_inst_details():
    """Fichier Excel des intervenants par UV avec détails

Les détails sont pris dans le fichiers de détails global. Les
affectations sont prises pour chaque UV.
    """

    def xls_inst_details(inst_uv, inst_details, target):
        inst_uv = pd.read_excel(inst_uv)
        inst_details = pd.read_excel(inst_details)

        # Add details from inst_details
        df = inst_uv.merge(inst_details, how='left',
                           left_on='Intervenants',
                           right_on='Intervenants')

        with Output(target) as target:
            df.to_excel(target(), index=False)

    insts_details = documents(task_xls_instructors.target)

    for planning, uv, info in selected_uv():
        inst_uv = documents(XlsAffectation.target, **info)
        target = generated(task_xls_inst_details.target, **info)
        yield {
            'name': f'{planning}_{uv}',
            'file_dep': [inst_uv, insts_details],
            'targets': [target],
            'actions': [(xls_inst_details, [inst_uv, insts_details, target])]
        }


@add_templates(
    target='remplacement.xlsx'
)
def task_xls_UTP():
    """Crée un document Excel pour calcul des heures et remplacements."""

    def xls_UTP(xls, details, target):
        df = pd.read_excel(xls)

        # Add details
        df_details = read_xls_details(details)

        if df['Intervenants'].isnull().all():
            return TaskFailed("Pas d'intervenants renseignés dans le fichier %s" % xls)
            # # read from raw file
            # with open(raw) as fd:
            #     instructors = [line.rstrip() for line in fd]
            #     df_insts = np.dataframe({'intervenants': instructors})
        else:
            # aggregate
            df_insts = create_insts_list(df)

        # add details from df_details
        df = df_insts.merge(df_details, how='left',
                            left_on='Intervenants',
                            right_on='Intervenants')

        dfs = df.sort_values(['Responsable', 'Statut', 'SortCourseList'],
                             ascending=False)
        dfs = dfs.reset_index()

        with Output(target, protected=True) as target:
            create_excel_file(target(), dfs)

    insts = documents(task_xls_instructors.target)
    for planning, uv, info in selected_uv():
        xls = documents(XlsAffectation.target, **info)
        target = generated(task_xls_UTP.target, **info)

        yield {
            'name': f'{planning}_{uv}',
            'file_dep': [xls, insts],
            'targets': [target],
            'actions': [(xls_UTP, [xls, insts, target])],
            'verbosity': 2
        }


class XlsAffectation(UVTask):
    """Fichier Excel des créneaux de toutes les UV configurées."""

    unique_uv = False
    target_name = "intervenants.xlsx"
    directory = "documents"

    # FIXME: remove
    target = "intervenants.xlsx"

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.uvlist_csv = documents(UtcUvListToCsv.target)
        self.file_dep = [self.uvlist_csv]
        self.target = XlsAffectation.build_target(planning, uv, info)

    def run(self):
        df = pd.read_csv(self.uvlist_csv)
        df_uv = df.loc[df['Code enseig.'] == self.uv, :]

        selected_columns = ['Jour', 'Heure début', 'Heure fin', 'Locaux',
                            'Semaine', 'Lib. créneau']
        df_uv = df_uv[selected_columns]
        df_uv = df_uv.sort_values(['Lib. créneau', 'Semaine'])

        df_uv['Intervenants'] = ''
        df_uv['Responsable'] = ''

        # Copy for modifications
        with Output(self.target, protected=True) as target:
            df_uv.to_excel(target(), sheet_name='Intervenants', index=False)


# @add_templates(target='intervenants.xlsx')
# def XlsAffectation():
#     """Fichier Excel des créneaux de toutes les UV configurées."""

#     def extract_uv_instructor(uv_list_filename, uv, target):
#         df = pd.read_csv(uv_list_filename)
#         df_uv = df.loc[df['Code enseig.'] == uv, :]

#         selected_columns = ['Jour', 'Heure début', 'Heure fin', 'Locaux',
#                             'Semaine', 'Lib. créneau']
#         df_uv = df_uv[selected_columns]
#         df_uv = df_uv.sort_values(['Lib. créneau', 'Semaine'])

#         df_uv['Intervenants'] = ''
#         df_uv['Responsable'] = ''

#         # Copy for modifications
#         with Output(target, protected=True) as target:
#             df_uv.to_excel(target(), sheet_name='Intervenants', index=False)

#     uvlist_csv = documents(UtcUvListToCsv.target)
#     for planning, uv, info in selected_uv():
#         target = documents(XlsAffectation.target, **info)

#         yield {
#             'name': f'{planning}_{uv}',
#             'file_dep': [uvlist_csv],
#             'targets': [target],
#             'actions': [(extract_uv_instructor, [uvlist_csv, uv, target])],
#             'verbosity': 2
#         }


@add_templates(target='emploi_du_temps.xlsx')
def task_xls_emploi_du_temps():
    "Sélection des créneaux pour envoi aux intervenants"

    def xls_emploi_du_temps(xls_details, xls_edt):
        df = pd.read_excel(xls_details)
        selected_columns = ['Jour', 'Heure début', 'Heure fin', 'Locaux',
                            'Semaine', 'Lib. créneau', 'Intervenants']
        dfs = df[selected_columns]

        with Output(xls_edt, protected=True) as xls_edt:
            dfs.to_excel(xls_edt(), sheet_name='Emploi du temps', index=False)

    for planning, uv, info in selected_uv():
        dep = documents(XlsAffectation.target, **info)
        target = generated(task_xls_emploi_du_temps.target, **info)
        yield {
            'name': f'{planning}_{uv}',
            'file_dep': [dep],
            'targets': [target],
            'actions': [(xls_emploi_du_temps, [dep, target])],
            'verbosity': 2
        }
