import os
import re
from datetime import timedelta, datetime, time
import json
import numpy as np
import pandas as pd
from PyPDF2 import PdfFileReader
from tabula import read_pdf
import pynliner

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
    get_unique_uv,
    action_msg,
    DATE_FORMAT,
    TIME_FORMAT,
    lib_list
)

from .scripts.moodle_date import CondDate, CondGroup, CondOr, CondAnd


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
                df = read_pdf(uv_list_filename, **tabula_args, pandas_options=pdo)

                if page == 1:
                    # Detect possible multiline header
                    header_height = ((re.match('[A-Z]{,3}[0-9]+', str(df.iloc[0, 0])) is None) +
                                     (re.match('[A-Z]{,3}[0-9]+', str(df.iloc[1, 0])) is None))
                    print(f'Header has {header_height} lines')
                    header = df.iloc[:header_height].fillna('').agg(['sum']).iloc[0]
                    df = df.iloc[header_height:]
                    df = df.rename(columns=header)
                    df = df.rename(columns={
                        'Activit': 'Activité',
                        'Type cr neau': 'Type créneau',
                        'Lib. cr': 'Lib. créneau',
                        'Lib.créneau': 'Lib. créneau',
                        'Heuredébut': 'Heure début',
                        'Heure d': 'Heure début',
                        'Heurefin': 'Heure fin'
                    })

                    print(f'Found {len(df.columns)} header column :')
                    print("\n".join(df.columns.values))
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


@add_templates(target='UTC_UV_list_créneau.csv')
@actionfailed_on_exception
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

    args = parse_args(
        task_csv_all_courses,
        argument('-p', '--plannings', nargs='+', default=settings.SELECTED_PLANNINGS)
    )

    return {
        'actions': [(csv_all_courses, [args.plannings, dep, target])],
        'file_dep': [dep],
        'targets': [target],
        'verbosity': 2
    }


@actionfailed_on_exception
def task_html_table():
    """Table HTML des TD/TP"""

    def html_table(planning, csv_inst_list, uv, courses, target, no_AB):
        # Select wanted slots
        slots = compute_slots(csv_inst_list, planning, filter_uvs=[uv])
        slots = slots[slots['Activité'].isin(courses)]

        # Fail if no slot
        if len(slots) == 0:
            if len(courses) > 1:
                return TaskFailed(f"Pas de créneau pour le planning `{planning}', l'uv `{uv}' et les cours `{', '.join(courses)}'")
            else:
                print(f"Pas de créneaux pour l'activité {courses[0]}")
                return

        def mondays(beg, end):
            while beg <= end:
                nbeg = beg + timedelta(days=7)
                yield (beg, nbeg)
                beg = nbeg

        def merge_slots(df):
            activity = df.iloc[0]["Activité"]

            if activity == 'Cours':
                return ', '.join(df.num.apply(str))
            elif activity == 'TD':
                return ', '.join(df.num.apply(str))
            elif activity == 'TP':
                if no_AB:
                    return ', '.join(df.num.apply(str))
                else:
                    return ', '.join(df.semaine + df.numAB.apply(str))
            else:
                raise Exception("Unrecognized activity", activity)

        # Iterate on each week of semester
        rows = []
        weeks = []
        for (mon, nmon) in mondays(settings.PLANNINGS[planning]['PL_BEG'],
                                   settings.PLANNINGS[planning]['PL_END']):
            weeks.append('{}-{}'.format(mon.strftime('%d/%m'),
                                        (nmon-timedelta(days=1)).strftime('%d/%m')))

            # Select slots on current week
            cr_week = slots.loc[(slots.date >= mon) & (slots.date < nmon)]
            if len(cr_week) > 0:
                e = cr_week.groupby('Lib. créneau').apply(merge_slots)
                rows.append(e)
            else:
                rows.append(pd.Series())

        # Weeks on rows
        df = pd.concat(rows, axis=1, sort=True).transpose()

        # Reorder columns
        if len(df.columns) > 1:
            cols = sorted(df.columns.tolist(), key=lib_list)
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

    args = parse_args(
        task_html_table,
        argument('-c', '--courses', nargs='*', default=["Cours", "TD", "TP"]),
        argument('-g', '--grouped', action='store_true'),
        argument('-a', '--no-AB', action='store_true')
    )

    from .dodo_instructors import task_add_instructors
    dep = generated(task_add_instructors.target)
    for planning, uv, info in selected_uv():
        if args.grouped:
            name = "_".join(args.courses)
            if args.grouped:
                name += "_grouped"
            if args.no_AB:
                name += "_no_AB"
            target = generated(f'{name}_table.html', **info)
            yield {
                'name': f'{planning}_{uv}_{name}',
                'file_dep': [dep],
                'actions': [(html_table, [
                    planning, dep, uv, args.courses, target, args.no_AB])],
                'targets': [target],
            }
        else:
            for course in args.courses:
                target = generated(f'{course}_table.html', **info)
                yield {
                    'name': f'{planning}_{uv}_{course}',
                    'file_dep': [dep],
                    'actions': [(html_table, [
                        planning, dep, uv, [course], target, args.no_AB])],
                    'targets': [target],
                    'verbosity': 2
                }


@actionfailed_on_exception
def task_json_restriction():
    """Ficher json des restrictions d'accès aux ressources sur Moodle
basées sur le début/fin des séances."""

    def restriction_list(csv, uv, course, AB, target):
        df = pd.read_csv(csv)
        df = df.loc[df['Code enseig.'] == uv]
        df = df.loc[df['Activité'] == course]
        gb = df.groupby(AB)

        def get_beg_end_date_each(num, df):
            def group_beg_end(row):
                if AB == "numAB":
                    group = row['Lib. créneau'] + row['semaine']
                else:
                    group = row['Lib. créneau']

                date = row['date']
                hd = row['Heure début']
                hf = row['Heure fin']
                dtd = datetime.strptime(date + "_" + hd, DATE_FORMAT + "_" + TIME_FORMAT)
                dtf = datetime.strptime(date + "_" + hf, DATE_FORMAT + "_" + TIME_FORMAT)

                return group, dtd, dtf

            gbe = [group_beg_end(row) for index, row in df.iterrows()]
            dt_min = min(b for g, b, e in gbe)
            dt_max = max(e for g, b, e in gbe)

            dt_min_monday = dt_min - timedelta(days=dt_min.weekday())
            dt_min_monday = datetime.combine(dt_min_monday, time.min)
            dt_min_midnight = datetime.combine(dt_min, time.min)
            after_beg_group = [(CondGroup() == g) & (CondDate() >= b) for g, b, e in gbe]
            before_beg_group = [(CondGroup() == g) & (CondDate() < b) for g, b, e in gbe]

            dt_max_friday = dt_max + timedelta(days=6 - dt_max.weekday())
            dt_max_friday = datetime.combine(dt_max_friday, time.max)
            dt_max_midnight = datetime.combine(dt_max, time.max)
            after_end_group = [(CondGroup() == g) & (CondDate() >= e) for g, b, e in gbe]
            before_end_group = [(CondGroup() == g) & (CondDate() < e) for g, b, e in gbe]

            group_id = settings.GROUP_ID
            return ("Séance " + str(num), {
                "début minuit": (CondDate() >= dt_min_midnight).to_PHP(group_id),
                "début": (CondDate() >= dt_min).to_PHP(group_id),
                "début lundi": (CondDate() >= dt_min_monday).to_PHP(group_id),
                "début par groupe": CondOr(after_beg_group).to_PHP(group_id),
                "fin minuit": (CondDate() >= dt_max_midnight).to_PHP(group_id),
                "fin": (CondDate() >= dt_max).to_PHP(group_id),
                "fin vendredi": (CondDate() >= dt_max_friday).to_PHP(group_id),
                "fin par groupe": CondOr(after_end_group).to_PHP(group_id),
                "créneaux par groupe": CondAnd([
                    CondOr(after_beg_group),
                    CondOr(before_end_group)
                ]).to_PHP(group_id)
            })

        moodle_date = dict(get_beg_end_date_each(name, g) for name, g in gb)

        with Output(target, protected=True) as target:
            with open(target(), 'w') as fd:
                s = (
                    "{\n" +
                    ",\n".join(
                        (
                            f'  "{slot}": {"{"}\n' +
                            ',\n'.join(
                                (
                                    f'    "{name}": {" " * (16 - len(name))}'
                                    + json.dumps(moodle_json, ensure_ascii=False)
                                )
                                for name, moodle_json in dates.items()
                            ) + "\n  }"
                            for slot, dates in moodle_date.items()
                        )
                    ) + "\n}"
                )
                print(s, file=fd)

    args = parse_args(
        task_json_restriction,
        argument('-c', '--course', default="TP", choices=["Cours", "TD", "TP"],
                 help="Type de séances considérées"),
        argument('-a', '--AB', action='store_true', help="Prise en compte des semaines A/B")
    )

    planning, uv, info = get_unique_uv()
    AB = "numAB" if args.AB else "num"
    course = args.course
    if AB == "numAB":
        target_fn = f"moodle_restrictions_{course}_AB.json"
    else:
        target_fn = f"moodle_restrictions_{course}.json"

    target = generated(target_fn, **info)
    dep = generated(task_csv_all_courses.target)

    return {
        'actions': [(restriction_list, [dep, uv, course, AB, target])],
        'file_dep': [dep],
        'targets': [target],
         'uptodate': [False]
    }
