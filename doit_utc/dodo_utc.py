import os
import re
from datetime import timedelta, datetime
import json
import numpy as np
import pandas as pd
from PyPDF2 import PdfFileReader
from tabula import read_pdf
import pynliner

from doit import get_var
from doit.exceptions import TaskFailed

from .config import settings

from .utils import (
    Output,
    add_templates,
    documents,
    generated,
    selected_uv,
    action_msg,
    create_cal_from_dataframe,
    compute_slots,
    DATE_FORMAT
)

from .scripts.moodle_date import CondDate, CondGroup, CondOr


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

            for i in range(npages):
                print(f'Processing page ({i+1}/{npages})')
                page = i + 1
                tabula_args = {'pages': page}
                if page == 1:
                    pdo = {}
                else:
                    pdo = {'header': None}

                df = read_pdf(uv_list_filename, pandas_options=pdo, **tabula_args)

                if page == 1:
                    df = df.rename(columns={'Activit': 'Activité',
                                            'Heure d': 'Heure début',
                                            'Type cr neau': 'Type créneau',
                                            'Lib. cr': 'Lib. créneau'})
                    unordered_cols = list(set(df.columns).intersection(set(possible_cols)))
                    cols_order = {k: i for i, k in enumerate(df.columns)}
                    cols = sorted(unordered_cols, key=lambda x: cols_order[x])
                    week_idx = cols.index('Semaine')
                    df = df[cols]
                    print('%d columns found' % len(df.columns))
                else:
                    print('%d columns found' % len(df.columns))
                    if len(df.columns) == len(cols) - 1:
                        df.insert(week_idx, 'Semaine', np.nan)
                    df.columns = cols

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

    deps = [uv_list_filename]
    if os.path.exists(ue_list_filename):
        deps.append(ue_list_filename)

    semester = settings.SEMESTER
    return {
        'file_dep': deps,
        'targets': [target],
        'actions': [(utc_uv_list_to_csv, [semester, uv_list_filename, ue_list_filename, target])],
        'verbosity': 2
    }


@add_templates(target='creneaux-UV-prov_P19.pdf')
def task_UTC_UV_list():
    doc = documents(task_UTC_UV_list.target)

    def UTC_UV_list(doc):
        if not os.path.exists(doc):
            return TaskFailed(f"Pas de fichier `{doc}'")

    return {
        'actions': [(UTC_UV_list, [doc])],
        'targets': [doc]
    }


@add_templates(target='calendrier.pdf')
def task_cal_uv():
    """Calendrier PDF global de l'UV.

Crée le calendrier des Cours/TD/TP de toutes les UV listées dans
SELECTED_UVS.
    """

    def create_cal_from_list(uv, uv_list_filename, target):
        df = pd.read_excel(uv_list_filename)
        # df_uv_real = df.loc[~pd.isnull(df['Intervenants']), :]
        df_uv_real = df
        df_uv_real['Code enseig.'] = uv

        text = r'{name} \\ {room} \\ {author}'
        return create_cal_from_dataframe(df_uv_real, text, target)

    jinja_dir = os.path.join(os.path.dirname(__file__), 'templates')
    template = os.path.join(jinja_dir, 'calendar_template.tex.jinja2')

    from .dodo_instructors import task_xls_affectation
    for planning, uv, info in selected_uv():
        uv_list = documents(task_xls_affectation.target, **info)
        target = generated(task_cal_uv.target, **info)

        yield {
            'name': f'{planning}_{uv}',
            'file_dep': [uv_list, template],
            'targets': [target],
            'actions': [(create_cal_from_list, [uv, uv_list, target])]
        }


@add_templates(target='UTC_UV_list_créneau.csv')
def task_csv_all_courses():
    "Fichier csv de tous les créneaux du semestre"

    def csv_all_courses(plannings, csv, target):
        df = pd.read_csv(csv)

        tables = []
        for planning_type in plannings:
            uvs = (settings.PLANNINGS[planning_type].get('UVS') or
                   settings.PLANNINGS[planning_type].get('UES'))
            df = compute_slots(csv, planning_type, filter_uvs=uvs)
            tables.append(df)

        dfm = pd.concat(tables)
        with Output(target) as target:
            dfm.to_csv(target(), index=False)

    from .dodo_instructors import task_add_instructors
    dep = generated(task_add_instructors.target)
    target = generated(task_csv_all_courses.target)

    plannings = get_var('plannings') or settings.SELECTED_PLANNINGS
    return {
        'actions': [(csv_all_courses, [plannings, dep, target])],
        'file_dep': [dep],
        'targets': [target],
        'verbosity': 2
    }


def task_html_table():
    """Table HTML des TD/TP"""

    def html_table(planning, csv_inst_list, uv, course, target):
        # Select wanted slots
        slots = compute_slots(csv_inst_list, planning, filter_uvs=[uv])
        slots = slots.loc[slots['Activité'] == course, :]

        # Fail if no slot
        if len(slots) == 0:
            return TaskFailed(f"Pas de créneau pour le planning `{planning}', l'uv `{uv}' et le cours `{course}'")

        # Merge when multiple slots on same week
        if course == 'TP':
            lb = lambda df: ', '.join(df.semaine + df.numAB.apply(str))
        elif course == 'TD':
            lb = lambda df: ', '.join(df.num.apply(str))
        elif course == 'Cours':
            lb = lambda df: ', '.join(df.num.apply(str))
            # def lb(df):
            #     if len(df.index) > 1:
            #         raise Exception('Plusieurs cours en une semaine')
            #     else:
        else:
            raise Exception("Unknown course")

        def mondays(beg, end):
            while beg <= end:
                nbeg = beg + timedelta(days=7)
                yield (beg, nbeg)
                beg = nbeg

        # Iterate on each week of semester
        rows = []
        weeks = []
        for (mon, nmon) in mondays(settings.PLANNINGS[planning]['PL_BEG'],
                                   settings.PLANNINGS[planning]['PL_END']):
            weeks.append('{}-{}'.format(mon.strftime('%d/%m'),
                                        (nmon-timedelta(days=1)).strftime('%d/%m')))

            # Select
            cr_week = slots.loc[(slots.date >= mon) & (slots.date < nmon)]
            if len(cr_week) > 0:
                e = cr_week.groupby('Lib. créneau').apply(lb)
                rows.append(e)
            else:
                rows.append(pd.Series())

        # Weeks on rows
        df = pd.concat(rows, axis=1, sort=True).transpose()

        # Reorder columns
        if len(df.columns) > 1:
            cols = sorted(df.columns.tolist(), key=lambda x: int(re.search('[0-9]+', x).group()))
            df = df[cols]

        # Give name to indexes
        df.columns.name = 'Séance'
        df.index = weeks
        df.index.name = 'Semaine'

        # Replace NaN
        df = df.fillna('—')

        dfs = df.style
        dfs = dfs.set_table_styles([
            dict(selector='th.row_heading', props=[('width', '100px')]),
            dict(selector="th", props=[("font-size", "small"),
                                       ("text-align", "center")])])\
                 .set_properties(**{
                     'width': '50px',
                     'text-align': 'center',
                     'valign': 'middle'})\
                 .set_table_attributes('align="center" cellspacing="10" cellpadding="2"')

        html = dfs.render()

        # Inline style for Moodle
        output = pynliner.fromString(html)

        with Output(target) as target:
            with open(target(), 'w') as fd:
                fd.write(output)

    from .dodo_instructors import task_add_instructors
    dep = generated(task_add_instructors.target)
    for planning, uv, info in selected_uv():
        for course, short in [('TD', 'D'), ('TP', 'T'), ('Cours', 'C')]:
            target = generated(f'{course}_table.html', **info)
            yield {
                'name': f'{planning}_{uv}_{course}',
                'file_dep': [dep],
                'actions': [(html_table, [planning, dep, uv, course, target])],
                'targets': [target],
                'verbosity': 2
            }


def task_json_restriction():
    """Ficher json des restrictions d'accès des TP"""

    def restriction_list(uv, csv, target):
        df = pd.read_csv(csv)
        df = df.loc[df['Code enseig.'] == uv]
        df = df.loc[df['Activité'] == 'TP']

        def get_beg_end_date_each(num, df):
            sts = []
            if num == 7:        # Exam
                return None
            if num == 6:        # Dispo juste après la séance
                dt_min = pd.to_datetime(df['date']).min().date()
                for _, row in df.iterrows():
                    group = row['Lib. créneau'] + row['semaine']
                    dt = (datetime.strptime(row['date'], DATE_FORMAT).date() +
                          timedelta(days=1))
                    sts.append((CondGroup() == group) & (CondDate() >= dt))

                return (num, {'enonce': (CondDate() >= dt_min).to_PHP(),
                              'corrige': CondOr(sts=sts).to_PHP()})

            else:               # Dispo après la dernière séance
                dt_min = pd.to_datetime(df['date']).min().date()
                dt_max = (pd.to_datetime(df['date']).max().date() +
                          timedelta(days=1))
                return (num, {'enonce': (CondDate() >= dt_min).to_PHP(),
                              'corrige': (CondDate() >= dt_max).to_PHP()})

        gb = df.groupby('numAB')
        moodle_date = dict([get_beg_end_date_each(name, g) for name, g in gb
                            if get_beg_end_date_each(name, g) is not None])

        with Output(target) as target:
            with open(target(), 'w') as fd:
                json.dump(moodle_date, fd, indent=4)

    dep = generated(task_csv_all_courses.target)

    uvs = list(selected_uv())
    if len(uvs) == 1:
        planning, uv, info = uvs[0]
        target = generated('moodle_date.json', **info)
        return {
            'actions': [(restriction_list, [uv, dep, target])],
            'file_dep': [dep],
            'verbosity': 2
        }
    else:
        return action_msg("Une seule UV doit être sélectionnée")
