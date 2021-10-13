"""
Ce module rassemble les tâches de création des créneaux officiels de
Cours/TD/TP.
"""

import os
import re
import numpy as np
import pandas as pd
from PyPDF2 import PdfFileReader
from tabula import read_pdf

from ..utils_config import Output, selected_uv, compute_slots
from ..utils import argument, rel_to_dir
from .base import CliArgsMixin, TaskBase


class UtcUvListToCsv(TaskBase):
    """Crée un fichier CSV des créneaux de toutes les UVs à partir du PDF"""

    hidden = True
    target_dir = "documents"
    target_name = "UTC_UV_list.csv"

    def setup(self):
        super().setup()

        if "CRENEAU_UV" in self.settings:
            self.uv_list_filename = os.path.join(
                self.settings.SEMESTER_DIR,
                self.settings.CRENEAU_UV
            )
        else:
            self.uv_list_filename = None

        if "CRENEAU_UE" in self.settings:
            self.ue_list_filename = os.path.join(
                self.settings.SEMESTER_DIR,
                self.settings.CRENEAU_UE
            )
        else:
            self.ue_list_filename = None

        self.target = self.build_target()

        self.file_dep = [
            fn
            for fn in [
                self.uv_list_filename,
                self.ue_list_filename
            ]
            if fn
        ]

    def read_pdf(self):
        pdf = PdfFileReader(open(self.uv_list_filename, 'rb'))
        npages = pdf.getNumPages()

        possible_cols = ['Code enseig.', 'Activité', 'Jour', 'Heure début',
                         'Heure fin', 'Semaine', 'Locaux', 'Type créneau',
                         'Lib. créneau', 'Responsable enseig.']

        tables = []
        pdo = {"header": None}
        for i in range(npages):
            print(f'Processing page ({i+1}/{npages})')
            page = i + 1
            tabula_args = {'pages': page}
            # Use pdo.copy(): pdo is changed by read_pdf
            df = read_pdf(self.uv_list_filename, **tabula_args, pandas_options=pdo.copy())[0]

            if page == 1:
                # Detect header (might be a two-line header)
                header_height = ((re.match('[A-Z]{,3}[0-9]+', str(df.iloc[0, 0])) is None) +
                                 (re.match('[A-Z]{,3}[0-9]+', str(df.iloc[1, 0])) is None))
                if header_height == 0:
                    raise Exception("No header detected")
                print(f'Detected header has {header_height} lines')

                # Compute single line/multiline header
                header = df.iloc[:header_height].fillna('').agg(['sum']).iloc[0]
                print("Header is:")
                print(" ".join(header))

                # Extract real data
                df = df.iloc[header_height:]

                # Set name of columns from header
                df = df.rename(columns=header)

                # Rename incorrectly parsed headers
                df = df.rename(columns={
                    'Activit': 'Activité',
                    'Type cr neau': 'Type créneau',
                    'Lib. cr': 'Lib. créneau',
                    'Lib.créneau': 'Lib. créneau',
                    'Lib.': 'Lib. créneau',
                    'Lib.\rcréneau': 'Lib. créneau',
                    'Heuredébut': 'Heure début',
                    'Heure d': 'Heure début',
                    'Heurefin': 'Heure fin',
                    'Locaux hybrides': "Locaux"
                })

                unknown_cols = list(set(df.columns) - set(possible_cols))
                if unknown_cols:
                    raise Exception("Colonnes inconnues détectées:", " ".join(unknown_cols))

                # Get list of detected columns
                cols = df.columns.to_list()

                # 'Semaine' is the only column that might not be
                # detected in next pages because it can be empty.
                # Store its index to insert a blank column if needed
                if "Semaine" in cols:
                    week_idx = cols.index('Semaine')
                else:
                    week_idx = cols.index('Heure fin') + 1

                print('%d columns found' % len(df.columns))
                print(" ".join(df.columns))
            else:
                print('%d columns found' % len(df.columns))

                # Semaine column might be empty and not detected
                if len(df.columns) == len(cols):
                    pass
                elif len(df.columns) == len(cols) - 1:
                    df.insert(week_idx, 'Semaine', np.nan)
                else:
                    raise Exception("Mauvais nombre de colonnes détectées")
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
        if self.uv_list_filename is None and self.ue_list_filename is None:
            raise Exception("Au moins une des variables `CRENEAU_UV` ou `CRENEAU_UE` doit être définie")

        tables = []

        # Lire tous les créneaux par semaine de toutes les UVs
        if self.uv_list_filename is not None:
            if os.path.exists(self.uv_list_filename):
                tables.append(self.read_pdf())
            else:
                uv_fn = rel_to_dir(self.uv_list_filename, self.settings.SEMESTER_DIR)
                raise Exception(f"Le fichier n'existe pas: {uv_fn}")

        # Lire les créneaux par semaine pour les masters
        if self.ue_list_filename is not None:
            if os.path.exists(self.ue_list_filename):
                try:
                    df_ue = pd.read_excel(self.ue_list_filename, engine="openpyxl")
                except ValueError as e:
                    ue_fn = rel_to_dir(self.ue_list_filename, self.settings.SEMESTER_DIR)
                    raise Exception(f"Erreur lors de la lecture du fichier Excel : {ue_fn}")

                columns = [
                    "Code enseig.",
                    "Activité",
                    "Jour",
                    "Heure début",
                    "Heure fin",
                    "Semaine",
                    "Locaux",
                    "Responsable enseig.",
                    "Lib. créneau",
                    "Planning"
                ]

                if len(df_ue.columns) != 10 or list(df_ue.columns) != columns:
                    msg = ", ".join(["`" + e + "`" for e in columns])
                    ue_fn = rel_to_dir(self.ue_list_filename, self.settings.SEMESTER_DIR)
                    raise Exception(f"Le fichier {ue_fn} doit être un fichier Excel avec exactement et dans cet ordre les colonnes: {msg}")

                tables.append(df_ue)
            else:
                ue_fn = rel_to_dir(self.ue_list_filename, self.settings.SEMESTER_DIR)
                raise Exception(f"Le fichier n'existe pas : {ue_fn}")

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

    hidden = True
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

    def setup(self):
        super().setup()
        from .instructors import AddInstructors
        self.csv = AddInstructors.target_from()
        self.file_dep = [self.csv]

        self.parse_args()
        self.target = self.build_target()
        if self.plannings is None:
            self.plannings = self.settings.SELECTED_PLANNINGS

    def run(self):
        tables = []
        for planning_type in self.plannings:
            uvs = (self.settings.PLANNINGS[planning_type].get('UVS') or
                   self.settings.PLANNINGS[planning_type].get('UES'))
            df = compute_slots(self.csv, planning_type, filter_uvs=uvs)
            tables.append(df)

        dfm = pd.concat(tables)
        with Output(self.target) as target:
            dfm.to_csv(target(), index=False)
