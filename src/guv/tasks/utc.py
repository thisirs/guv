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
import openpyxl

from ..openpyxl_patched import fixit

fixit(openpyxl)

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows
from ..openpyxl_utils import fill_row, get_cell_in_row

from ..logger import logger
from ..utils import argument
from ..utils_config import Output, compute_slots, selected_uv, rel_to_dir, ask_choice
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

        self.target = self.build_target()

        if self.uv_list_filename is not None:
            self.file_dep = [self.uv_list_filename]
        else:
            self.file_dep = []

    def read_pdf(self):
        pdf = PdfFileReader(open(self.uv_list_filename, 'rb'))
        npages = pdf.getNumPages()

        possible_cols = ['Code enseig.', 'Activité', 'Jour', 'Heure début',
                         'Heure fin', 'Semaine', 'Locaux', 'Type créneau',
                         'Lib. créneau', 'Responsable enseig.']

        tables = []
        pdo = {"header": None}
        for i in range(npages):
            logger.info("Processing page (%d/%d)", i+1, npages)
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
                logger.info("Detected header has %d lines", header_height)

                # Compute single line/multiline header
                header = df.iloc[:header_height].fillna('').agg(['sum']).iloc[0]
                logger.info("Header is: %s", ' '.join(header))

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

                logger.info("%d columns found", len(df.columns))
                logger.info(" ".join(df.columns))
            else:
                logger.info("%d columns found", len(df.columns))

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
                logger.info("Header has %d lines", header_height)
                df = df.iloc[header_height:]

            tables.append(df)

        return pd.concat(tables)

    def run(self):
        if self.uv_list_filename is None:
            raise Exception("La variable `CRENEAU_UV` doit être définie")

        tables = []

        # Lire tous les créneaux par semaine de toutes les UVs
        if self.uv_list_filename is not None:
            if os.path.exists(self.uv_list_filename):
                tables.append(self.read_pdf())
            else:
                uv_fn = rel_to_dir(self.uv_list_filename, self.settings.SEMESTER_DIR)
                raise Exception(f"Le fichier n'existe pas: {uv_fn}")

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
                            choice = ask_choice(
                                f'Semaine pour le créneau {row["Lib. créneau"]} de TP de {group.name[0]} (A ou B) ? ',
                                choices={"A": "A", "a": "A", "B": "B", "b": "B"},
                            )
                            group.loc[index, "Semaine"] = choice
                    else:
                        group.loc[nans.index, 'Semaine'] = 'A'
                return group
            else:
                return group

        df = df.groupby(['Code enseig.', 'Activité']).apply(fix_semaineAB)

        with Output(self.target) as out:
            df.to_csv(out.target, index=False)


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
        from .instructors import WeekSlotsAll
        self.week_slots_all = WeekSlotsAll.target_from()
        self.file_dep = [self.week_slots_all]

        self.parse_args()
        self.target = self.build_target()
        if self.plannings is None:
            self.plannings = self.settings.SELECTED_PLANNINGS

    def run(self):
        tables = []
        for planning_type in self.plannings:
            uvs = (self.settings.PLANNINGS[planning_type].get('UVS') or
                   self.settings.PLANNINGS[planning_type].get('UES'))
            df = compute_slots(self.week_slots_all, planning_type, filter_uvs=uvs)
            tables.append(df)

        dfm = pd.concat(tables)
        with Output(self.target) as out:
            dfm.to_csv(out.target, index=False)


class UTP(TaskBase):
    target_dir = "."
    target_name = "UTP.xlsx"

    def setup(self):
        super().setup()
        self.target = self.build_target()

    def write_UV_block(self, ref_cell):
        keywords = [
            "UV",
            "Cours",
            "Nombre de créneaux de 2h par semaine",
            "Heures",
            "UTP"
        ]

        # Write header
        end_cell = fill_row(ref_cell, *keywords)

        # Define references to header
        cell_in_row = get_cell_in_row(ref_cell, *keywords)

        def get_mult(cell):
            return 'IF({0}="CM",2.25,IF({0}="TD",1.5,IF({0}="TP",1.5,0))'.format(cell.coordinate)

        UTP_cells = []
        for i in range(16):
            cell = ref_cell.below(i + 1)
            elts = [
                None,
                None,
                None,
                lambda cell: "=2*16*{}".format(cell_in_row(cell, "Nombre de créneaux de 2h par semaine").coordinate),
                lambda cell: "={}*{}".format(cell_in_row(cell, "Heures").coordinate, get_mult(cell_in_row(cell, "Cours")))
            ]
            UTP_cell = fill_row(cell, *elts)
            UTP_cells.append(UTP_cell)

    def run(self):
        wb = Workbook()
        ws = wb.active

        ref_cell = ws.cell(2, 2)
        self.write_UV_block(ref_cell)

        ref_cell = ws.cell(2, 8)
        self.write_hour_block(ref_cell)

        with Output(self.target, protected=True) as out:
            wb.save(out.target)

    def write_hour_block(self, ref_cell):
        keywords = [
            "UV",
            "Cours",
            "Nombre d'heures",
            "UTP"
        ]

        # Write header
        end_cell = fill_row(ref_cell, *keywords)

        # Define references to header
        cell_in_row = get_cell_in_row(ref_cell, *keywords)

        def get_mult(cell):
            return 'IF({0}="CM",2.25,IF({0}="TD",1.5,IF({0}="TP",1.5,0))'.format(cell.coordinate)

        UTP_cells = []
        for i in range(16):
            cell = ref_cell.below(i + 1)
            elts = [
                None,
                None,
                None,
                lambda cell: "={}*{}".format(cell_in_row(cell, "Nombre d'heures").coordinate, get_mult(cell_in_row(cell, "Cours")))
            ]
            UTP_cell = fill_row(cell, *elts)
            UTP_cells.append(UTP_cell)

