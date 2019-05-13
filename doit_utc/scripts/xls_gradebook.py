__doc__ = """
Create an Excel file to compute grades
"""

import os
import sys
import math
import argparse

from collections import OrderedDict
from openpyxl import Workbook
from openpyxl import utils
from openpyxl.cell import Cell
from openpyxl.worksheet import Worksheet
from openpyxl.styles import Alignment, PatternFill
from openpyxl.formatting.rule import CellIsRule
from openpyxl.utils.cell import absolute_coordinate

import pandas as pd
import oyaml as yaml            # Ordered yaml

# Custom navigation functions
def left(self, step=1):
    return self.offset(0, -step)

def right(self, step=1):
    return self.offset(0, step)

def above(self, step=1):
    return self.offset(-step, 0)

def below(self, step=1):
    return self.offset(step, 0)

def text(self, value):
    self.value = value
    return self


Cell.left = left
Cell.right = right
Cell.above = above
Cell.below = below
Cell.text = text


def merge_cells2(self, cell1, cell2):
    return self.merge_cells(
        start_row=cell1.row,
        start_column=cell1.col_idx,
        end_row=cell2.row,
        end_column=cell2.col_idx
    )


Worksheet.merge_cells2 = merge_cells2


def walk_tree(tree, depth=None, start_at=0):
    def compute_depth(tree):
        if isinstance(tree, (OrderedDict, dict)):
            return 1 + max(compute_depth(child) for child in tree.values())
        else:
            return 1

    if depth is None:
        depth = compute_depth(tree)

    class RunOut(Exception):
        pass

    def walk_tree0(name, tree, current_depth, nleaves):
        if isinstance(tree, (OrderedDict, dict)):  # Inner node
            current_leaves = 0
            sdepth = None
            x_span = None
            for key, child in tree.items():
                try:
                    yield from walk_tree0(key, child, current_depth + 1, nleaves + current_leaves)
                except RunOut as e:
                    nleaf, sdepth = e.args
                    current_leaves += nleaf
                    x_span = math.ceil(sdepth // (current_depth + 1))
                    sdepth = sdepth - x_span
            if current_depth != 0:
                yield name, nleaves, sdepth, current_leaves, x_span
                raise RunOut(current_leaves, sdepth)
        else:                   # Leave
            x_span = math.ceil((depth + 1) // (current_depth + 1))
            sdepth = depth - x_span
            yield name, nleaves, sdepth, 1, x_span
            raise RunOut(1, sdepth)

    yield from walk_tree0('root', tree, 0, 0)


class GradeSheetWriter:
    def __init__(self, argv):
        self.init_parser()
        self.parse_args(argv)

        # Store name of gradesheet
        if self.args.name:
            self.name = self.args.name

        # Setting source of grades
        if self.args.data_file:
            if os.path.isdir(self.args.data_file):
                if self.args.planning is None or self.args.uv is None:
                    raise Exception('Need uv and planning')
                fn = f'{self.args.planning}_{self.args.uv}_student_data_merge.xlsx'
                self.data_file = os.path.join(self.args.data_file, fn)
            else:
                self.data_file = self.args.data_file
        else:
            self.data_file = f'{self.args.planning}_{self.args.uv}_student_data_merge.xlsx'

        # Reading source of grades
        if not os.path.exists(self.data_file):
            raise Exception(f'Data file `{self.data_file}` does not exist')
        self.data_df = pd.read_excel(self.data_file)

        # Setting path of current gradebook
        if self.args.output_file:
            if os.path.isdir(self.args.output_file):
                fn = f'{self.args.name}_gradebook.xlsx'
                self.output_file = os.path.join(self.args.output_file, fn)
            else:
                self.output_file = self.args.output_file
        else:
            self.output_file = f'{self.args.name}_gradebook.xlsx'

        # Write workbook with columns from data
        self.wb = Workbook()
        self.ws_data = self.wb.active
        self.ws_data.title = "data"
        self.df = pd.DataFrame()
        columns = self.get_columns(**self.args.__dict__)

        for i, (name, type) in enumerate(columns.items()):
            idx = i + 1
            # Write header of column with Pandas style
            self.ws_data.cell(1, idx).value = name
            self.ws_data.cell(1, idx).style = "Pandas"

            # Copy data from DATA_DF if existing
            if name in self.data_df.columns:
                for i, value in enumerate(self.data_df[name]):
                    self.ws_data.cell(i + 2, idx, value)

            # Copy data or cells in DF
            N = len(self.data_df.index)
            if type == 'cell':
                cells = self.ws_data[utils.get_column_letter(idx)][1:(N+1)]
                self.df[name] = cells
            elif type == 'value':
                if name not in self.data_df.columns:
                    raise Exception('No data to copy from and type is data')
                self.df[name] = self.data_df[name]
            else:
                raise Exception("Unsupported type: {}".format(type))

    def parse_args(self, argv):
        self.args = self.parser.parse_args(argv)

    def init_parser(self):
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument('--type', dest='type', required=True)
        self.parser.add_argument('--name', dest='name', required=True)
        self.parser.add_argument('--uv', dest='uv')
        self.parser.add_argument('--planning', dest='planning')
        self.parser.add_argument('-d', '--data', dest='data_file')
        self.parser.add_argument('-o', '--output-file', dest='output_file')

    def get_columns(self, **kwargs):
        return {
            'Nom': 'value',
            'Prénom': 'value',
            'Courriel': 'value',
            self.name: 'cell'
        }

    def write(self):
        raise NotImplementedError


# class GradeSheetWriter:
#     def __init__(self, argv):
#         self._init_parser()
#         self.args = self.parser.parse_args(argv)

#         if self.args.name:
#             self.name = self.args.name

#         if self.args.data_file:
#             if os.path.isdir(self.args.data_file):
#                 if self.args.planning is None or self.args.uv is None:
#                     raise Exception('Need uv and planning')
#                 fn = f'{self.args.planning}_{self.args.uv}_student_data_merge.xlsx'
#                 self.data_file = os.path.join(self.args.data_file, fn)
#             else:
#                 self.data_file = self.args.data_file
#         else:
#             self.data_file = f'{self.args.planning}_{self.args.uv}_student_data_merge.xlsx'

#         if not os.path.exists(self.data_file):
#             raise Exception(f'Data file `{self.data_file}` does not exist')
#         self.df = pd.read_excel(self.data_file)

#         if self.args.output_file:
#             if os.path.isdir(self.args.output_file):
#                 fn = f'{self.args.planning}_{self.args.uv}_{self.args.name}_gradebook.xlsx'
#                 self.output_file = os.path.join(self.args.output_file, fn)
#             else:
#                 self.output_file = self.args.output_file
#         else:
#             self.output_file = f'{self.args.planning}_{self.args.uv}_{self.args.name}_gradebook.xlsx'

#         filtered_columns = self.filtered_columns(**self.args.__dict__)
#         if filtered_columns is None:
#             self.filtered_df = self.df
#         else:
#             self.filtered_df = self.df[filtered_columns]

#         self.filtered_df.to_excel(self.output_file, index=False)
#         self.wb = load_workbook(self.output_file)
#         ws_data = self.wb.active
#         ws_data.title = "data"

#         # Create new column and worksheet
#         self.gradesheet = self.wb.create_sheet(title=self.name)
#         newcol_idx = ws_data.max_column + 1
#         ws_data.cell(1, newcol_idx).value = self.name
#         cell = ws_data.cell(1, 1)
#         ws_data.cell(1, newcol_idx)._style = copy(cell._style)

#         # Add list of cells
#         cells = ws_data[utils.get_column_letter(newcol_idx)][1:]
#         self.filtered_df[self.name] = cells

#     def _init_parser(self):
#         self.parser = argparse.ArgumentParser()
#         self.parser.add_argument('--type', dest='type', required=True)
#         self.parser.add_argument('--name', dest='name', required=True)
#         self.parser.add_argument('--uv', dest='uv')
#         self.parser.add_argument('--planning', dest='planning')
#         self.parser.add_argument('-d', '--data', dest='data_file')
#         self.parser.add_argument('-o', '--output-file', dest='output_file')

#     def filtered_columns(self, **kwargs):
#         return ['Nom', 'Prénom', 'Courriel']

#     def write(self):
#         raise NotImplementedError


class GradeSheetSimpleWriter(GradeSheetWriter):
    def write(self, ref=None):
        # Write new gradesheet
        self.gradesheet = self.wb.create_sheet(title=self.name)

        if ref is None:
            ref = (3, 1)
        row, col = ref

        for i, (index, record) in enumerate(self.df.iterrows()):
            self.gradesheet.cell(ref[0]-2, col+i+1, record['Nom'])
            self.gradesheet.cell(ref[0]-1, col+i+1, record['Prénom'])
            record[self.gradesheet.title].value = "='{}'!{}{}".format(
                self.gradesheet.title,
                utils.get_column_letter(col+i+1).upper(),
                row+1)

        self.wb.save(self.output_file)


class GradeSheetExamWriter(GradeSheetWriter):
    """Feuille de notes pour un examen type médian/final avec des
questions structurées."""

    def __init__(self, argv):
        super(GradeSheetExamWriter, self).__init__(argv)
        self.tree = self.read_structure(self.args.struct)

    def init_parser(self):
        super(GradeSheetExamWriter, self).init_parser()
        self.parser.add_argument('-s', '--struct', required=True, dest='struct')

    def read_structure(self, structure):
        "On cherche dans STRUCTURE et dans le sous-dossier documents/."
        if os.path.exists(structure):
            struct_path = structure
        else:
            struct_path = os.path.join('documents', structure)
            if not os.path.exists(struct_path):
                raise Exception(f'Path to {structure} or {struct_path} not existing')

        with open(struct_path, "r") as stream:
            return list(yaml.load_all(stream))[0]

    def write_structure(self, upper_left):
        "Write structure at UPPER_LEFT and return lower right cell."
        maxi = maxj = -1

        for name, i, j, di, dj in walk_tree(self.tree):
            maxi = max(maxi, i+di)
            maxj = max(maxj, j+dj)
            self.gradesheet.merge_cells(
                start_row=upper_left[0]+i,
                start_column=upper_left[1]+j,
                end_row=upper_left[0]+i+di-1,
                end_column=upper_left[1]+j+dj-1)
            self.gradesheet.cell(
                row=upper_left[0]+i,
                column=upper_left[1]+j).value = name
            al = Alignment(horizontal="center", vertical="center")
            self.gradesheet.cell(
                row=upper_left[0]+i,
                column=upper_left[1]+j).alignment = al

        return maxi + upper_left[0] - 1, maxj + upper_left[1] - 1

    def write(self, ref=None):
        # Write new gradesheet
        self.gradesheet = self.wb.create_sheet(title=self.name)

        if ref is None:
            ref = (3, 1)
        row, col = self.write_structure(upper_left=ref)

        for i, (index, record) in enumerate(self.df.iterrows()):
            self.gradesheet.cell(ref[0]-2, col+i+1, record['Nom'])
            self.gradesheet.cell(ref[0]-1, col+i+1, record['Prénom'])

            # On lie le total des points à la cellule note dans la
            # feuille récapitulative
            record[self.gradesheet.title].value = "='{}'!{}{}".format(
                self.gradesheet.title,
                utils.get_column_letter(col+i+1).upper(),
                row+1)

            # On écrit le total des points pour former la note globale
            range = (
                utils.get_column_letter(col+i+1) + str(ref[0]) +
                ':' +
                utils.get_column_letter(col+i+1) + str(row)
            )
            formula = f'=IF(COUNTBLANK({range})>0, "", SUM({range}))'

            self.gradesheet.cell(row+1, col+i+1, formula)

        self.wb.save(self.output_file)


class GradeSheetExamMultipleWriter(GradeSheetExamWriter):
    """Feuille de notes avec barème et liste des correcteurs."""

    def __init__(self, argv):
        super().__init__(argv)
        self.tree = self.read_structure(self.args.struct)
        insts_file = self.args.insts
        df = pd.read_excel(insts_file)
        insts = df['Intervenants'].unique()

        def select_inst(i):
            while True:
                try:
                    choice = input(f'Sélectionner le correcteur {i} (y/n)? ')
                    if choice.upper() == "Y":
                        print(f"Correcteur {i} sélectionné")
                        return True
                    elif choice.upper() == "N":
                        print(f"Correcteur {i} non sélectionné")
                        return False
                    else:
                        raise ValueError
                except ValueError:
                    continue
                else:
                    break

        self.insts = [i for i in insts if select_inst(i)]

    def init_parser(self):
        super().init_parser()
        self.parser.add_argument('-i', '--instructors', required=True, dest='insts')

    def get_columns(self, **kwargs):
        return {
            'Nom': 'value',
            'Prénom': 'value',
            'Courriel': 'value',
            'Note': 'cell',
            "Correcteur": 'cell',
        }

    def write(self, ref=None):
        if ref is None:
            ref = (3, 1)

        for inst in self.insts:
            self.gradesheet = self.wb.create_sheet(title=inst)

            row, col = self.write_structure(upper_left=ref)
            self.gradesheet.cell(row+1, col, "Note")

            # On fige les colonnes après le barème
            self.gradesheet.freeze_panes = self.gradesheet.cell(1, col+1).coordinate

            for i, (index, record) in enumerate(self.df.iterrows()):
                self.gradesheet.cell(ref[0]-2, col+i+1, record['Nom'])
                self.gradesheet.cell(ref[0]-1, col+i+1, record['Prénom'])

                # On écrit le total des points pour former la note globale
                range = (
                    utils.get_column_letter(col+i+1) + str(ref[0]) +
                    ':' +
                    utils.get_column_letter(col+i+1) + str(row)
                )
                formula = f'=IF(COUNTBLANK({range})>0, "", SUM({range}))'

                self.gradesheet.cell(row+1, col+i+1, formula)

        # Formula to return first non empty cell
        grade_format = '""'
        for inst in self.insts:
            cell = "'{}'!{{0}}{{1}}".format(inst)
            grade_format = f"IF({cell} = \"\", {grade_format}, {cell})"

        # Formula to return first instructor
        inst_format = '""'
        for inst in self.insts:
            cell = "'{}'!{{0}}{{1}}".format(inst)
            inst_format = f"IF({cell} = \"\", {inst_format}, \"{inst}\")"
        # inst_format = "CONCATENATE(\"Corrigé par \", {})".format(inst_format)

        # List of booleans of non empty cells from each sheet
        non_empty_grades = ["IF('{}'!{{0}}{{1}} <> \"\", 1, 0)".format(inst)
                            for inst in self.insts]
        non_empty_grades = ", ".join(non_empty_grades)

        for i, (index, record) in enumerate(self.df.iterrows()):
            formula = "=IF(SUM({0}) = 0, \"\", IF(SUM({0}) = 1, {1}, NA())".format(
                non_empty_grades.format(
                    utils.get_column_letter(col+i+1).upper(),
                    row+1
                ),
                grade_format.format(
                    utils.get_column_letter(col+i+1).upper(),
                    row+1
                )
            )
            record["Note"].value = formula

            formula = "=IF(SUM({0}) = 0, \"\", IF(SUM({0}) = 1, {1}, NA())".format(
                non_empty_grades.format(
                    utils.get_column_letter(col+i+1).upper(),
                    row+1
                ),
                inst_format.format(
                    utils.get_column_letter(col+i+1).upper(),
                    row+1
                )
            )
            record["Correcteur"].value = formula

        self.wb.save(self.output_file)


class GradeSheetSimpleGroup(GradeSheetSimpleWriter):
    """Simple gradesheet per groups, no subgrading"""

    def __init__(self, argv):
        super(GradeSheetSimpleGroup, self).__init__(argv)
        self.group = self.args.group

    def get_columns(self, **kwargs):
        return {
            'Nom': 'value',
            'Prénom': 'value',
            'Courriel': 'value',
            kwargs['group']: 'value',
            self.name: 'cell'
        }

    def init_parser(self):
        super(GradeSheetSimpleGroup, self).init_parser()
        self.parser.add_argument('-g', '--group', required=True, dest='group')

    def write(self, ref=None):
        # Write new gradesheet
        self.gradesheet = self.wb.create_sheet(title=self.name)

        header_ref_cell = self.gradesheet['B1']
        header_ref_cell.below().left().text("Note").below().text("Correction")

        for i, (key, group) in enumerate(self.df.groupby(self.group)):
            # Group name
            self.gradesheet.merge_cells2(
                header_ref_cell.right(2*i),
                header_ref_cell.right(2*i+1))
            header_ref_cell.right(2*i).value = key

            # Note
            self.gradesheet.merge_cells2(
                header_ref_cell.right(2*i).below(),
                header_ref_cell.right(2*i+1).below())

            for j, (index, record) in enumerate(group.iterrows()):
                name = record['Nom'] + ' ' + record['Prénom']
                header_ref_cell.right(2*i).below(2+j).value = name

                record[self.name].value = "='{}'!{}+'{}'!{}".format(
                    self.gradesheet.title,
                    header_ref_cell.right(2*i).below().coordinate,
                    self.gradesheet.title,
                    header_ref_cell.right(2*i+1).below(2+j).coordinate)

        self.wb.save(self.output_file)


class GradeSheetAssignmentWriter(GradeSheetExamWriter):
    def __init__(self, argv):
        super(GradeSheetAssignmentWriter, self).__init__(argv)
        self.group = self.args.group

    def get_columns(self, **kwargs):
        return {
            'Nom': 'value',
            'Prénom': 'value',
            'Courriel': 'value',
            kwargs['group']: 'value',
            self.name: 'cell'
        }

    def init_parser(self):
        super(GradeSheetAssignmentWriter, self).init_parser()
        self.parser.add_argument('-g', '--group', required=True, dest='group')

    def write(self, ref=None):
        # Write new gradesheet
        self.gradesheet = self.wb.create_sheet(title=self.name)

        if ref is None:
            ref = (3, 1)
        row, col = self.write_structure(upper_left=ref)

        for i, (key, group) in enumerate(self.df.groupby(self.group)):
            group_names = ', '.join(group['Nom'] + ' ' + group['Prénom'])
            self.gradesheet.cell(ref[0]-2, col+i+1, key)
            self.gradesheet.cell(ref[0]-1, col+i+1, group_names)

            formula = (
                '=SUM(' +
                utils.get_column_letter(col+i+1) + str(ref[0]) +
                ':' +
                utils.get_column_letter(col+i+1) + str(row) +
                ')'
            )
            self.gradesheet.cell(row+1, col+i+1, formula)

            for index, record in group.iterrows():
                record[self.name].value = "='{}'!{}{}".format(
                    self.gradesheet.title,
                    utils.get_column_letter(col+i+1).upper(),
                    str(row+1))

        self.wb.save(self.output_file)


class GradeSheetJuryWriter(GradeSheetWriter):
    def __init__(self, argv):
        super(GradeSheetJuryWriter, self).__init__(argv)

    def parse_args(self, argv):
        self.args = self.parser.parse_args(argv)
        self.config = self.parse_config(self.args.config)

    def get_columns(self, **kwargs):
        columns = {
            'Nom': 'value',
            'Prénom': 'value',
            'Courriel': 'value',
            'Admis': 'cell',
            'Note admis': 'cell'
        }

        for name, opts in self.config['columns'].items():
            if opts.get('cell'):
                columns[name] = 'cell'
            else:
                columns[name] = 'value'

        columns['Note ECTS'] = 'cell'
        return columns

    def init_parser(self):
        super(GradeSheetJuryWriter, self).init_parser()
        self.parser.add_argument('-c', '--config', required=True, dest='config')

    def parse_config(self, config):
        if not os.path.exists(config):
            raise Exception("Configuration file not found")

        with open(config, "r") as stream:
            return list(yaml.load_all(stream))[0]

    def get_address_of_cell(self, cell, absolute=False, force=False, compat=False):
        parent = cell.parent
        current = self.wb.active
        if parent == current and not force:
            if absolute:
                return absolute_coordinate(cell.coordinate)
            else:
                return cell.coordinate
        else:
            if absolute:
                coordinate = absolute_coordinate(cell.coordinate)
            else:
                coordinate = cell.coordinate
            if compat:
                return "INDIRECT(\"'{}'!{}\")".format(parent.title, coordinate)
            else:
                return "'{}'!{}".format(parent.title, coordinate)

    def get_range_of_cells(self, colname):
        if colname not in self.df.columns:
            raise Exception('Unknown column name: {}'.format(colname))

        cells = self.df[colname]
        first, last = cells.iloc[0], cells.iloc[-1]

        if first.parent == self.wb.active:
            return '{}:{}'.format(first.coordinate, last.coordinate)
        else:
            return "'{}'!{}:'{}'!{}".format(
                first.parent.title,
                first.coordinate,
                first.parent.title,
                last.coordinate)

    def write(self, ref=None):
        # Write new gradesheet
        self.gradesheet = self.wb.create_sheet(title=self.name)

        # On écrit les grandeurs utiles pour les différents calculs
        ref = (1, 1)
        keytocell = {}
        for i, (name, settings) in enumerate(self.config['columns'].items()):
            self.gradesheet.cell(ref[0] + i, ref[1], name)
            ne = settings.get('note_éliminatoire', -1)
            self.gradesheet.cell(ref[0] + i, ref[1] + 1, ne)
            key = name + '_note_éliminatoire'
            keytocell[key] = self.gradesheet.cell(ref[0] + i, ref[1] + 1)

        for name, value in self.config['options'].items():
            i += 1
            self.gradesheet.cell(ref[0] + i, ref[1], name)
            self.gradesheet.cell(ref[0] + i, ref[1] + 1, value)
            keytocell[name] = self.gradesheet.cell(ref[0] + i, ref[1] + 1)

        # On écrit la note agrégée
        self.wb.active = self.ws_data
        # for i, (index, record) in enumerate(self.df.iterrows()):
        #     record['Note agrégée'].value = (
        #         '=IFERROR({}/6+{}/2+{}/3, ""'.format(
        #             self.get_address_of_cell(record['Note_TP']),
        #             self.get_address_of_cell(record['Note final']),
        #             self.get_address_of_cell(record['Note médian'])
        #         )
        #     )

        # On écrit la note des admis uniquement pour le calcul des
        # percentiles
        self.wb.active = self.ws_data
        for i, (index, record) in enumerate(self.df.iterrows()):
            record['Note admis'].value = (
                '=IF({}=1, {}, "")'.format(
                    self.get_address_of_cell(record['Admis']),
                    self.get_address_of_cell(record['Note agrégée'])
                )
            )

        # On écrit les seuils des notes correspondants aux percentiles choisis
        self.wb.active = self.gradesheet
        ref = (20, 1)           # En dessous des infos
        self.gradesheet.cell(ref[0], ref[1], "Barres")
        for i, ects in enumerate('ABCD'):
            key = 'Percentile note ' + ects
            percentile_cell = keytocell[key]
            self.gradesheet.cell(ref[0] + i, ref[1], ects + " si >=")
            self.gradesheet.cell(ref[0] + i, ref[1] + 1).value = (
                '=PERCENTILE({}, {})'.format(
                    self.get_range_of_cells('Note admis'),
                    self.get_address_of_cell(percentile_cell, absolute=True)
                )
            )
            keytocell['barre_' + ects] = self.gradesheet.cell(ref[0] + i, ref[1] + 1)

        # On écrit la colonnes des admis/refusés
        self.wb.active = self.ws_data
        for i, (index, record) in enumerate(self.df.iterrows()):
            ifs = []
            for name, settings in self.config['columns'].items():
                key = name + '_note_éliminatoire'
                ifs.append("IF({}+0>={}, 1)".format(
                    self.get_address_of_cell(record[name]),
                    self.get_address_of_cell(keytocell[key], absolute=True)))
            record['Admis'].value = f"=IFERROR({'*'.join(ifs)}, 0)"

        # On écrit un bloc détaillant le nombre d'admis et le ratio en
        # fonction de la colonne `Admis`
        self.wb.active = self.gradesheet
        ref = (1, 4)
        self.gradesheet.cell(ref[0], ref[1], 'Proportions')
        self.gradesheet.cell(ref[0]+1, ref[1], 'Nombre d\'admis')
        self.gradesheet.cell(ref[0]+1, ref[1]+1,).value = (
            "=SUM({})".format(
                self.get_range_of_cells('Admis')
            )
        )
        self.gradesheet.cell(ref[0]+2, ref[1], 'Ratio')
        self.gradesheet.cell(ref[0]+2, ref[1]+1,).value = (
            "=AVERAGE({})".format(
                self.get_range_of_cells('Admis')
            )
        )

        # On écrit la note ECTS en fonction des autres notes
        self.wb.active = self.ws_data
        for i, (index, record) in enumerate(self.df.iterrows()):
            record['Note ECTS'].value = (
                '=IF({}="RESERVE", "RESERVE", IF({}="ABS", "ABS", IF({}=0, "F", IF({}>={}, "A", IF({}>={}, "B", IF({}>={}, "C", IF({}>={}, "D", "E")))))))'.format(
                    self.get_address_of_cell(record['Note agrégée']),
                    self.get_address_of_cell(record['Note agrégée']),
                    self.get_address_of_cell(record['Admis']),
                    self.get_address_of_cell(record['Note agrégée']),
                    self.get_address_of_cell(keytocell['barre_A'], absolute=True),
                    self.get_address_of_cell(record['Note agrégée']),
                    self.get_address_of_cell(keytocell['barre_B'], absolute=True),
                    self.get_address_of_cell(record['Note agrégée']),
                    self.get_address_of_cell(keytocell['barre_C'], absolute=True),
                    self.get_address_of_cell(record['Note agrégée']),
                    self.get_address_of_cell(keytocell['barre_D'], absolute=True)
                )
            )
        for cell in self.df["Note ECTS"]:
            cell.alignment = Alignment(horizontal='center')

        range = self.get_range_of_cells('Note ECTS')
        for ects, color in zip('ABCDEF', [
                '00FF00',
                '58FF00',
                'C2FF00',
                'FFD300',
                'FF6900',
                'FF0000'
        ]):
            fill = PatternFill(start_color=color, end_color=color, fill_type='solid')
            rule = CellIsRule(operator='equal', formula=[f'"{ects}"'], fill=fill)
            self.ws_data.conditional_formatting.add(range, rule)

        # On écrit les proportions de notes ECTS en fonction de la
        # colonne `Admis`
        self.wb.active = self.gradesheet
        ref = (1, 7)
        self.gradesheet.cell(ref[0], ref[1], 'Proportions')
        for i, ects in enumerate('ABCDEF'):
            self.gradesheet.cell(ref[0] + i + 1, ref[1], ects)
            self.gradesheet.cell(ref[0] + i + 1, ref[1] + 1).value = (
                '=COUNTIF({}, "{}")'
            ).format(
                self.get_range_of_cells('Note ECTS'),
                ects
            )

        # Formattage conditionnel pour les notes éliminatoires
        self.wb.active = self.ws_data
        redFill = PatternFill(start_color='EE1111',
                              end_color='EE1111',
                              fill_type='solid')

        for name, opts in self.config['columns'].items():
            if opts.get('note_éliminatoire'):
                id = name + '_note_éliminatoire'
                if id in keytocell:
                    threshold_cell = keytocell[id]
                    threshold_addr = self.get_address_of_cell(
                        threshold_cell,
                        absolute=True,
                        force=True,
                        compat=True)
                    self.ws_data.conditional_formatting.add(
                        self.get_range_of_cells(name),
                        CellIsRule(operator='lessThan',
                                   formula=[threshold_addr],
                                   fill=redFill))

        # On offre la possibilité de trier
        self.wb.active = self.ws_data
        max_column = self.ws_data.max_column
        max_row = self.ws_data.max_row
        self.ws_data.auto_filter.ref = 'A1:{}{}'.format(
            utils.get_column_letter(max_column),
            max_row)
        range = self.get_range_of_cells('Note ECTS')
        self.ws_data.auto_filter.add_sort_condition(range)

        # On fige la première ligne
        self.ws_data.freeze_panes = "A2"

        # On sauve le classeur
        self.wb.save(self.output_file)


WRITERS = {
    'exam': GradeSheetExamWriter,
    'exammult': GradeSheetExamMultipleWriter,
    'assignment': GradeSheetAssignmentWriter,
    'simple': GradeSheetSimpleWriter,
    'jury': GradeSheetJuryWriter,
    'group': GradeSheetSimpleGroup
}


def arg(argv):
    "Get path of data file from command line"
    try:
        if '--type' in argv:
            type = argv[argv.index('--type') + 1]
        else:
            raise Exception(f'No assignment type provided, allowed types: {", ".join(WRITERS.keys())}')

        if type not in WRITERS.keys():
            raise Exception(f'Type `{type}` not recognized, allowed types: {", ".join(WRITERS.keys())}')

        writerklass = WRITERS[type]
        writer = writerklass(argv)
        return writer.data_file
    except:
        return []


def run(argv=sys.argv[1:]):
    if '--type' in argv:
        type = argv[argv.index('--type') + 1]
    else:
        raise Exception(f'No assignment type provided, allowed types: {", ".join(WRITERS.keys())}')

    if type not in WRITERS.keys():
        raise Exception(f'Type `{type}` not recognized, allowed types: {", ".join(WRITERS.keys())}')

    writerklass = WRITERS[type]
    writer = writerklass(argv)
    writer.write()


if __name__ == '__main__':
    # run("--type assignment --group TPE -s median.yaml --name bar -d ../generated --uv SY02 --planning P2018".split())
    # run("--type simple --name bar -d ../generated --uv SY02 --planning P2018".split())
    # run("--type jury --name bar -c config.yaml -d ../generated --uv SY02 --planning P2018".split())
    run('-h')
