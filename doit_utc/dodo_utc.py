"""
Fichier qui regroupe les tâches de création des créneaux officiels de
Cours/TD/TP.
"""

import os
import re
import numpy as np
import pandas as pd
from PyPDF2 import PdfFileReader
from tabula import read_pdf

from .utils_config import Output, selected_uv, compute_slots
from .utils import argument, rel_to_dir
from .tasks import CliArgsMixin, TaskBase


class UtcUvListToCsv(TaskBase):
    """Crée un fichier CSV à partir de la liste d'UV au format PDF"""

    target_dir = "documents"
    target_name = "UTC_UV_list.csv"

    def __init__(self):
        super().__init__()
        self.uv_list_filename = os.path.join(
            self.settings.SEMESTER_DIR,
            self.settings.CRENEAU_UV
        )

        self.ue_list_filename = os.path.join(
            self.settings.SEMESTER_DIR,
            "documents",
            "UTC_UE_list.xlsx"
        )

        self.target = self.build_target()

        self.file_dep = [
            fn
            for fn in [
                self.uv_list_filename,
                self.ue_list_filename
            ]
            if os.path.exists(fn)
        ]

    def read_pdf(self):
        pdf = PdfFileReader(open(self.uv_list_filename, 'rb'))
        npages = pdf.getNumPages()

        possible_cols = ['Code enseig.', 'Activité', 'Jour', 'Heure début',
                         'Heure fin', 'Semaine', 'Locaux', 'Type créneau',
                         'Lib. créneau', 'Responsable enseig.']

        tables = []
        pdo = {'header': None}
        for i in range(npages):
            print(f'Processing page ({i+1}/{npages})')
            page = i + 1
            tabula_args = {'pages': page}
            df = read_pdf(self.uv_list_filename, **tabula_args, pandas_options=pdo)[0]

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

            df['Planning'] = self.settings.SEMESTER
            tables.append(df)

        return pd.concat(tables)

    def run(self):
        if not self.file_dep:
            uv_fn = rel_to_dir(self.uv_list_filename, self.settings.SEMESTER_DIR)
            ue_fn = rel_to_dir(self.ue_list_filename, self.settings.SEMESTER_DIR)
            msg = f"Au moins un des fichiers {uv_fn} ou {ue_fn} doit être disponible."
            raise Exception(msg)

        tables = []

        # Lire tous les créneaux par semaine de toute les UVs
        if os.path.exists(self.uv_list_filename):
            tables.append(self.read_pdf())

        # Lire les créneaux par semaine pour les masters
        if os.path.exists(self.ue_list_filename):
            tables.append(pd.read_excel(self.ue_list_filename))

        df = pd.concat(tables)

        # Remove duplicate indexes from concat
        df.reset_index(drop=True, inplace=True)

        # T1 instead of T 1
        df['Lib. créneau'].replace(' +', '', regex=True, inplace=True)

        # A ou B au lieu de semaine A et semaine B
        df['Semaine'].replace("^semaine ([AB])$", "\\1", regex=True, inplace=True)

        # Semaine ni A ni B pour les TP: demander
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

        with Output(self.target) as target:
            df.to_csv(target(), index=False)


class CsvAllCourses(CliArgsMixin, TaskBase):
    "Fichier csv de tous les créneaux du semestre"

    unique_uv = False
    target_dir = "generated"
    target_name = "UTC_UV_list_créneau.csv"
    cli_args = (
        argument(
            "-p",
            "--plannings",
            nargs="+",
            help="Liste des plannings à considérer",
        ),
    )

    def __init__(self):
        super().__init__()
        from .dodo_instructors import AddInstructors
        self.csv = AddInstructors.target_from()
        self.target = self.build_target()
        self.file_dep = [self.csv]
        if self.plannings is None:
            self.plannings = self.settings.SELECTED_PLANNINGS

    def run(self):
        df = pd.read_csv(self.csv)

        tables = []
        for planning_type in self.plannings:
            uvs = (self.settings.PLANNINGS[planning_type].get('UVS') or
                   self.settings.PLANNINGS[planning_type].get('UES'))
            df = compute_slots(self.csv, planning_type, filter_uvs=uvs)
            tables.append(df)

        dfm = pd.concat(tables)
        with Output(self.target) as target:
            dfm.to_csv(target(), index=False)
