__doc__ = """
Create Excel files
"""

from openpyxl import Workbook
from openpyxl.cell import Cell
from openpyxl import utils
from openpyxl.styles import PatternFill

import numpy as np

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


def create_excel_file(filename, df):
    wb = Workbook()
    ws_remp = wb.active
    ws_remp.title = "remplacements"

    C_total = create_double_entry_table(ws_remp, 'A1', df,
                                        'a remplacé x séances de Cours')

    coord = ws_remp['A1'].below(len(df.index) + 2).coordinate
    TD_total = create_double_entry_table(ws_remp, coord, df,
                                         'a remplacé x séances de TD')

    coord = ws_remp[coord].below(len(df.index) + 2).coordinate
    TP_total = create_double_entry_table(ws_remp, coord, df,
                                         'a remplacé x séances de TP')

    ws_sum = wb.create_sheet(title="heures")
    create_summary_table(ws_sum, 'A1', df, ws_remp, C_total, TD_total, TP_total)
    wb.save(filename)


def create_double_entry_table(ws, reference, df, title):
    ws[reference] = title
    ref = utils.coordinate_to_tuple(reference)

    instructors = df['Intervenants'].values

    # Diagonale grisée
    solid = PatternFill(fill_type='solid', bgColor='00000000')
    for i in range(len(instructors)):
        ws.cell(row=ref[0]+1+i, column=ref[1]+1+i).fill = solid

    # En-tête ligne et colonne
    ws.column_dimensions[utils.get_column_letter(ref[1])].width = 20
    for i, instructor in enumerate(instructors):
        ws.column_dimensions[utils.get_column_letter(ref[1]+1+i)].width = 20
        ws.cell(row=ref[0]+1+i, column=ref[1]).value = instructor
        ws.cell(row=ref[0], column=ref[1]+1+i).value = instructor

    inst_to_cellsm = {}
    inst_to_cellsp = {}
    for k, inst in enumerate(instructors):
        cellsp = []
        cellsm = []
        for i in range(len(instructors)):
            if k == i:
                continue
            cell = utils.get_column_letter(ref[1]+1+i)+str(ref[0]+1+k)
            cellsp.append(cell)
        cellsp = '+'.join(cellsp)
        inst_to_cellsp[inst] = cellsp

        for i in range(len(instructors)):
            if k == i:
                continue
            cell = utils.get_column_letter(ref[1]+1+k)+str(ref[0]+1+i)
            cellsm.append(cell)
        cellsm = '+'.join(cellsm)
        inst_to_cellsm[inst] = cellsm

    # Balance des séances
    total_col = ref[1]+len(instructors)+1
    ws.cell(row=ref[0], column=total_col).value = 'Balance'

    inst_to_total = {}
    for i in range(len(instructors)):
        inst = instructors[i]
        formule = '={}-({})'.format(inst_to_cellsp[inst], inst_to_cellsm[inst])
        ws.cell(row=ref[0]+i+1, column=total_col).value = formule
        cell = '{}{}'.format(utils.get_column_letter(total_col), ref[0]+i+1)
        inst_to_total[inst] = cell

    # Total des échanges en absolu
    total_col = ref[1]+len(instructors)+2
    ws.cell(row=ref[0], column=total_col).value = 'Échange'

    for i in range(len(instructors)):
        inst = instructors[i]
        formule = '={}+{}'.format(inst_to_cellsp[inst], inst_to_cellsm[inst])
        ws.cell(row=ref[0]+i+1, column=total_col).value = formule

    return inst_to_total


def create_summary_table(ws, reference, df, ws_remp, C_total, TD_total, TP_total):
    def fill_row(refcell, elements):
        n = len(elements)
        for i in range(n):
            cell = ws.cell(row=refcell.row, column=refcell.col_idx + i)
            value = elements[i]
            if callable(value):
                value = value(cell)
            cell.value = value

    refcell = ws[reference]

    fill_row(refcell, ['Intervenants', 'Statut', 'Cours', 'TD', 'TP',
                       'Heures Cours prév', 'Heures TD prév', 'Heures TP prév',
                       'UTP prév', 'Remp. Cours', 'Remp. TD', 'Remp. TP',
                       'Heures Cours finales', 'Heures TD finales', 'Heures TP finales',
                       'UTP finales'])

    statut_mult = {
        'MCF': 1.5,
        'PR': 1.5,
        'PRAG': 1.5,
        'PRCE': 1.5,
        'PAST': 1.5,
        'ECC': 1.5,
        'Doct': 1.5,
        'ATER': 1,
        'Vacataire': 1,
        np.nan: 1
    }

    for i, row in df.iterrows():
        cell = refcell.below(i+1)
        inst = row['Intervenants']
        statut = row['Statut']
        elts = [inst,
                statut_mult[statut],
                row['Cours'],
                row['TD'],
                row['TP'],
                lambda cell: "=2*16*{}".format(cell.left(3).coordinate),
                lambda cell: "=2*16*{}".format(cell.left(3).coordinate),
                lambda cell: "=2*16*{}".format(cell.left(3).coordinate),
                lambda cell: "=2*16*2.25*{}+2*16*1.5*{}+2*16*{}*{}".format(
                    cell.left(6).coordinate,
                    cell.left(5).coordinate,
                    cell.left(4).coordinate,
                    cell.left(7).coordinate),
                '={}!{}'.format(ws_remp.title, C_total[inst]),
                '={}!{}'.format(ws_remp.title, TD_total[inst]),
                '={}!{}'.format(ws_remp.title, TP_total[inst]),
                lambda cell: "={}+2*{}".format(
                    cell.left(7).coordinate,
                    cell.left(3).coordinate),
                lambda cell: "={}+2*{}".format(
                    cell.left(7).coordinate,
                    cell.left(3).coordinate),
                lambda cell: "={}+2*{}".format(
                    cell.left(7).coordinate,
                    cell.left(3).coordinate),
                lambda cell: "=2.25*{} + 1.5*{} + {}*{}".format(
                    cell.left(3).coordinate,
                    cell.left(2).coordinate,
                    cell.left(1).coordinate,
                    cell.left(14).coordinate)]
        fill_row(cell, elts)

    cell = refcell.below(len(df.index)+1)

    solid = PatternFill(fill_type='solid', bgColor='00000000')
    fill_row(cell, [
        'Total',
        lambda cell: setattr(cell, 'fill', solid),
        lambda cell: "=SUM({}:{})".format(cell.above(len(df.index)).coordinate, cell.above().coordinate),
        lambda cell: "=SUM({}:{})".format(cell.above(len(df.index)).coordinate, cell.above().coordinate),
        lambda cell: "=SUM({}:{})".format(cell.above(len(df.index)).coordinate, cell.above().coordinate),
    ])

    fill_row(cell.below(), [
        'Prévision',
        lambda cell: setattr(cell, 'fill', solid)
    ])

    fill_row(cell.below().below(), [
        'Manque',
        lambda cell: setattr(cell, 'fill', solid),
        lambda cell: "={}-{}".format(cell.above().coordinate, cell.above(2).coordinate),
        lambda cell: "={}-{}".format(cell.above().coordinate, cell.above(2).coordinate),
        lambda cell: "={}-{}".format(cell.above().coordinate, cell.above(2).coordinate),
    ])

    fill_row(cell.below(3), [
        'Manque (UTP)',
        lambda cell: setattr(cell, 'fill', solid),
        lambda cell: "=2*2.25*16*{}".format(cell.above().coordinate),
        lambda cell: "=2*1.5*16*{}".format(cell.above().coordinate),
        lambda cell: "=2*1.5*16*{}".format(cell.above().coordinate),
    ])

    fill_row(cell.below(4), [
        'Manque (UTP)',
        lambda cell: setattr(cell, 'fill', solid),
        lambda cell: setattr(cell, 'fill', solid),
        lambda cell: setattr(cell, 'fill', solid),
        lambda cell: "=2*16*{}".format(cell.above(2).coordinate),
    ])
