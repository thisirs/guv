import os
import re
import numpy as np
import pandas as pd
from PyPDF2 import PdfFileReader
from tabula import read_pdf

from doit.exceptions import TaskFailed

from .config import settings

from .utils import (
    Output,
    add_templates,
    documents,
    generated,
    selected_uv,
    compute_slots,
    actionfailed_on_exception,
    parse_args,
    argument,
    action_msg,
)
from .tasks import CliArgsMixin, TaskBase


@add_templates(target='UTC_UV_list.csv')
def task_utc_uv_list_to_csv():
    """Crée un fichier CSV à partir de la liste d'UV au format PDF."""

    def utc_uv_list_to_csv(semester, uv_list_filename, ue_list_filename, target):
        tables = []

        if os.path.exists(uv_list_filename):
            # Nombre de pages
            pdf = PdfFileReader(open(uv_list_filename, 'rb'))
            npages = pdf.getNumPages()

            possible_cols = ['Code enseig.', 'Activité', 'Jour', 'Heure début',
                             'Heure fin', 'Semaine', 'Locaux', 'Type créneau',
                             'Lib. créneau', 'Responsable enseig.']

            pdo = {'header': None}
            for i in range(npages):
                print(f'Processing page ({i+1}/{npages})')
                page = i + 1
                tabula_args = {'pages': page}
                df = read_pdf(uv_list_filename, **tabula_args, pandas_options=pdo)[0]

                if page == 1:
                    # Detect if header has not been properly detected
                    header_height = ((re.match('[A-Z]{,3}[0-9]+', str(df.iloc[0, 0])) is None) +
                                     (re.match('[A-Z]{,3}[0-9]+', str(df.iloc[1, 0])) is None))
                    print(f'Header has {header_height} lines')

                    # Compute single line/multiline header
                    header = df.iloc[:header_height].fillna('').agg(['sum']).iloc[0]

                    # Strip header
                    df = df.iloc[header_height:]

                    # Set name of column from header
                    df = df.rename(columns=header)

                    # Rename incorrectly parsed headers
                    df = df.rename(columns={
                        'Activit': 'Activité',
                        'Type cr neau': 'Type créneau',
                        'Lib. cr': 'Lib. créneau',
                        'Lib.créneau': 'Lib. créneau',
                        'Lib.\rcréneau': 'Lib. créneau',
                        'Heuredébut': 'Heure début',
                        'Heure d': 'Heure début',
                        'Heurefin': 'Heure fin'
                    })

                    unordered_cols = list(set(df.columns).intersection(set(possible_cols)))
                    cols_order = {k: i for i, k in enumerate(df.columns)}
                    cols = sorted(unordered_cols, key=lambda x: cols_order[x])

                    if "Semaine" in cols:
                        week_idx = cols.index('Semaine')
                    else:
                        week_idx = cols.index('Heure fin') + 1

                    df = df[cols]
                    print('%d columns found' % len(df.columns))
                else:
                    print('%d columns found' % len(df.columns))
                    if len(df.columns) == len(cols) - 1:
                        df.insert(week_idx, 'Semaine', np.nan)
                    df.columns = cols

                    # Detect possible multiline header
                    header_height = ((re.match('[A-Z]{,3}[0-9]+', str(df.iloc[0, 0])) is None) +
                                     (re.match('[A-Z]{,3}[0-9]+', str(df.iloc[1, 0])) is None))
                    print(f'Header has {header_height} lines')
                    df = df.iloc[header_height:]

                df['Planning'] = semester
                tables.append(df)

        if os.path.exists(ue_list_filename):
            df_ue = pd.read_excel(ue_list_filename)
            tables.append(df_ue)

        df = pd.concat(tables)

        # Remove duplicate indexes from concat
        df.reset_index(drop=True, inplace=True)

        # T1 instead of T 1
        df['Lib. créneau'].replace(' +', '', regex=True, inplace=True)

        # A ou B au lieu de semaine A et semaine B
        df['Semaine'].replace("^semaine ([AB])$", "\\1", regex=True, inplace=True)

        # Semaine ni A ni B pour les TP: mettre à A
        uvs = [uv for _, uv, _ in selected_uv(all=True)]

        def fix_semaineAB(group):
            if group.name[1] == 'TP' and len(group.index) > 1:
                nans = group.loc[(pd.isnull(group['Semaine']))]
                if 0 < len(nans.index) or len(nans.index) < len(group.index):
                    if group.name[0] in uvs:
                        for index, row in nans.iterrows():
                            while True:
                                try:
                                    choice = input(f'Semaine pour le créneau {row["Lib. créneau"]} de TP de {group.name[0]} (A ou B) ? ')
                                    if choice.upper() in ['A', 'B']:
                                        group.loc[index, 'Semaine'] = choice.upper()
                                    else:
                                        raise ValueError
                                except ValueError:
                                    continue
                                else:
                                    break
                    else:
                        group.loc[nans.index, 'Semaine'] = 'A'
                return group
            else:
                return group

        df = df.groupby(['Code enseig.', 'Activité']).apply(fix_semaineAB)

        with Output(target) as target:
            df.to_csv(target(), index=False)

    uv_list_filename = documents(task_UTC_UV_list.target)
    ue_list_filename = documents('UTC_UE_list.xlsx')
    target = documents(task_utc_uv_list_to_csv.target)

    deps = []
    if os.path.exists(uv_list_filename):
        deps.append(uv_list_filename)
    if os.path.exists(ue_list_filename):
        deps.append(ue_list_filename)

    if deps:
        semester = settings.SEMESTER
        return {
            'file_dep': deps,
            'targets': [target],
            'actions': [(utc_uv_list_to_csv, [semester, uv_list_filename, ue_list_filename, target])],
            'verbosity': 2
        }
    else:
        uv_fn = documents(task_UTC_UV_list.target, local=True)
        ue_fn = documents('UTC_UE_list.xlsx', local=True)
        msg = f"Au moins un des fichiers {uv_fn} ou {ue_fn} doit être disponible."
        return action_msg(msg, targets=[target])


@add_templates(target=settings.CRENEAU_UV)
def task_UTC_UV_list():
    """Dépendance vers le fichier CRENEAU_UV"""

    doc = documents(task_UTC_UV_list.target)

    def UTC_UV_list(doc):
        if not os.path.exists(doc):
            return TaskFailed(f"Pas de fichier `{doc}'")

    return {
        'actions': [(UTC_UV_list, [doc])],
        'targets': [doc]
    }


class CsvAllCourses(CliArgsMixin, TaskBase):
    "Fichier csv de tous les créneaux du semestre"

    target = "UTC_UV_list_créneau.csv"
    cli_args = argument(
        "-p",
        "--plannings",
        nargs="+",
        default=settings.SELECTED_PLANNINGS,
        help="Liste des plannings à considérer",
    )

    def __init__(self):
        super().__init__()
        from .dodo_instructors import task_add_instructors
        self.csv = generated(task_add_instructors.target)

        self.file_dep = [self.csv]
        self.targets = [generated(self.target, **self.info)]

    def run(self):
        df = pd.read_csv(self.csv)

        tables = []
        for planning_type in self.plannings:
            uvs = (settings.PLANNINGS[planning_type].get('UVS') or
                   settings.PLANNINGS[planning_type].get('UES'))
            df = compute_slots(self.csv, planning_type, filter_uvs=uvs)
            tables.append(df)

        dfm = pd.concat(tables)
        with Output(self.target) as target:
            dfm.to_csv(target(), index=False)
