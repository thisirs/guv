import os
import sys
from shutil import copyfile
import re
import markdown
import pynliner
import numpy as np
import pandas as pd
from pandas.api.types import CategoricalDtype
from icalendar import Event, Calendar
from datetime import datetime, date, timedelta
from tabula import read_pdf
import latex
import jinja2
import json

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"


def object_hook(obj):
    if '_type' not in obj:
        return obj
    type = obj['_type']
    if type == 'datetime':
        return datetime.strptime(obj['value'],
                                 DATE_FORMAT + ' ' + TIME_FORMAT)
    elif type == 'date':
        return datetime.strptime(obj['value'], DATE_FORMAT).date()
    elif type == 'DataFrame':
        return pd.read_json(obj['value'])
    return obj


json._default_decoder = json.JSONDecoder(
    object_pairs_hook=None,
    object_hook=object_hook)


def json_encoder_default(self, obj):
    if isinstance(obj, pd.DataFrame):
        return {
            "_type": "DataFrame",
            "value": obj.to_json()
        }
    elif isinstance(obj, datetime):
        return {
            "_type": "datetime",
            "value": obj.strftime("%s %s" % (
                DATE_FORMAT, TIME_FORMAT
            ))
        }
    elif isinstance(obj, date):
        return {
            "_type": "date",
            "value": obj.strftime(DATE_FORMAT)
        }
    return json.JSONEncoder.default(self, obj)


json.JSONEncoder.default = json_encoder_default


CONFIG = {
    'UV': ['SY02', 'SY09'],
    'PL_BEG': date(2018, 2, 19),
    'PL_END': date(2018, 6, 22),
    'SEMESTER': 'P2018'
}


def read_xls_details(fn):
    """Lit un fichier Excel avec un ordre sur le statut"""

    sts = ['MCF', 'PR', 'PRAG', 'PRCE', 'PAST', 'ECC', 'Doct', 'ATER',
           'Vacataire']
    status_type = CategoricalDtype(categories=sts, ordered=True)

    return pd.read_excel(fn, dtype={
        'Statut': status_type
    })


def task_xls_inst_details():
    """Fichier Excel des intervenants par UV avec détails"""

    def xls_inst_details(inst_uv, inst_details, target):
        inst_uv = pd.read_excel(inst_uv)
        inst_details = pd.read_excel(inst_details)

        # Add details from inst_details
        df = inst_uv.merge(inst_details, how='left',
                           left_on='Intervenants',
                           right_on='Intervenants')

        df.to_excel(target, index=False)

    insts_details = 'documents/intervenants.xlsx'
    for uv in CONFIG['UV']:
        inst_uv = f'documents/{uv}_intervenants_rempli.xlsx'
        target = f'generated/{uv}_intervenants_details.xlsx'
        if os.path.exists(inst_uv):
            yield {
                'name': uv,
                'file_dep': [inst_uv, insts_details],
                'targets': [target],
                'actions': [(xls_inst_details, [inst_uv, insts_details, target])]
            }


def create_insts_list(df):
    "Agrège les données d'affectation des Cours/TD/TP"

    def course_list(e):
        "Return course list like C1, D2, T1A"

        def lib_list(lib):
            m = re.match('([CDT])([0-9]*)([AB]*)', lib)
            crs = {'C': 0, 'D': 1, 'T': 2}[m.group(1)]
            no = int('0' + m.group(2))
            sem = 0 if m.group(3) == 'A' else 1
            return (crs, no, sem)

        return ', '.join(sorted(e, key=lib_list))

    def score(libs):
        sc = [0, 0, 0]
        for lib in libs:
            ix = {'C': 0, 'D': 1, 'T': 2}[re.search('[CDT]', lib).group()]
            sc[ix] += 1
        return tuple(sc)

    def myapply(df):
        e = df['Lib. créneau'] + df['Semaine'].fillna('')
        resp = int(df['Responsable'].sum())
        return pd.Series({
            'CourseList': course_list(e),
            'SortCourseList': score(e),
            'Responsable': resp
        })

    df = df.groupby('Intervenants')
    df = df.apply(myapply)
    df = df.reset_index()

    return(df)


def task_xls_UTP():
    """Crée un document Excel pour calcul des heures et remplacements."""

    sys.path.append('scripts/')
    from excel_hours import create_excel_file

    def xls_UTP(uv, xls, raw, details, target):
        df = pd.read_excel(xls)

        # Add details
        df_details = read_xls_details(details)

        if df['Intervenants'].isnull().all():
            # Read from raw file
            with open(raw) as fd:
                instructors = [line.rstrip() for line in fd]
                df_insts = np.DataFrame({'Intervenants': instructors})
        else:
            # Aggregate
            df_insts = create_insts_list(df)

        # Add details from df_details
        df = df_insts.merge(df_details, how='left',
                            left_on='Intervenants',
                            right_on='Intervenants')

        dfs = df.sort_values(['Responsable', 'Statut', 'SortCourseList'],
                             ascending=False)
        dfs = dfs.reset_index()

        create_excel_file(target, dfs[['Intervenants', 'Statut']])

        if os.path.exists(f'documents/{uv}_remplacement_rempli.xlsx'):
            print(f'documents/{uv}_remplacement_rempli.xlsx obsolète')
        else:
            copyfile(target, f'documents/{uv}_remplacement_rempli.xlsx')

    for uv in CONFIG['UV']:
        xls = f'documents/{uv}_intervenants_rempli.xlsx'
        raw = f'documents/{uv}_intervenants.raw'
        details = f'documents/intervenants.xlsx'
        target = f'generated/{uv}_remplacement.xlsx'
        yield {
            'name': uv,
            'file_dep': [xls, details],
            'targets': [target],
            'actions': [(xls_UTP, [uv, xls, raw, details, target])],
            'verbosity': 2
        }


def task_utc_uv_list_to_csv():
    "Crée un fichier CSV à partir de la liste d'UV au format PDF."

    def utc_uv_list_to_csv(uv_list_filename, target):
        # Extraire toutes les pages
        tabula_args = {'pages': 'all'}
        df = read_pdf(uv_list_filename, **tabula_args)

        # On renomme les colonnes qui sont mal passées
        df = df.rename(columns={'Activit': 'Activité',
                                'Heure d': 'Heure début',
                                'Type cr neau': 'Type créneau',
                                'Lib. cr': 'Lib. créneau'})

        # On enlève les fausses colonnes
        cols = ['Code enseig.', 'Activité', 'Jour', 'Heure début', 'Heure fin',
                'Semaine', 'Locaux', 'Type créneau', 'Lib. créneau']
        df = df[cols]

        # On enlève les fausses lignes en-têtes
        df = df.loc[df['Code enseig.'] != 'Code enseig.', :]

        # A ou B au lieu de semaine A et semaine B
        df['Semaine'].replace("^semaine ([AB])$", "\\1", regex=True, inplace=True)

        # T1 instead of T 1
        df['Lib. créneau'].replace(' +', '', regex=True, inplace=True)

        df.to_csv(target, index=False)

    uv_list_filename = 'documents/UTC_UV_list.pdf'
    target = 'generated/UTC_UV_list.csv'

    return {
        'file_dep': [uv_list_filename],
        'targets': [target],
        'actions': [(utc_uv_list_to_csv, [uv_list_filename, target])]
    }


def task_xls_affectation():
    """Fichier Excel des créneaux de toutes les UV configurées."""

    def extract_uv_instructor(uv_list_filename, uv, target):
        df = pd.read_csv(uv_list_filename)
        df_uv = df.loc[df['Code enseig.'] == uv, :]
        df_uv_real = df_uv.loc[df['Type créneau'] == 'Groupe actif', :]

        selected_columns = ['Jour', 'Heure début', 'Heure fin', 'Locaux',
                            'Semaine', 'Lib. créneau']
        df_uv_real = df_uv_real[selected_columns]
        df_uv_real['Intervenants'] = ''
        df_uv_real['Responsable'] = ''

        # Copy for modifications
        df_uv_real.to_excel(target, sheet_name='Intervenants', index=False)

        if os.path.exists(f'documents/{uv}_intervenants_rempli.xlsx'):
            print(f'documents/{uv}_intervenants_rempli.xlsx obsolète')
        else:
            copyfile(target, f'documents/{uv}_intervenants_rempli.xlsx')

    for uv in CONFIG['UV']:
        uvlist_csv = 'generated/UTC_UV_list.csv'
        target = f'generated/{uv}_intervenants.xlsx'

        yield {
            'name': uv,
            'file_dep': [uvlist_csv],
            'targets': [target],
            'actions': [(extract_uv_instructor, [uvlist_csv, uv, target])],
            'verbosity': 2
        }


def task_xls_emploi_du_temps():
    "Sélection des créneaux pour envoi aux intervenants"

    def xls_emploi_du_temps(xls_details, xls_edt):
        df = pd.read_excel(xls_details)
        selected_columns = ['Jour', 'Heure début', 'Heure fin', 'Locaux',
                            'Semaine', 'Lib. créneau', 'Intervenants']
        dfs = df[selected_columns]
        dfs.to_excel(xls_edt, sheet_name='Emploi du temps', index=False)

    for uv in CONFIG['UV']:
        if os.path.exists(f'documents/{uv}_intervenants_rempli.xlsx'):
            dep = f'documents/{uv}_intervenants_rempli.xlsx'
            target = f'generated/{uv}_emploi_du_temps.xlsx'
            yield {
                'name': uv,
                'file_dep': [dep],
                'targets': [target],
                'actions': [(xls_emploi_du_temps, [dep, target])],
                'verbosity': 2
            }


def task_html_inst():
    "Génère la description des intervenants pour Moodle"

    def html_inst(xls_uv, xls_details, target):
        df_uv = pd.read_excel(xls_uv)
        df_uv = create_insts_list(df_uv)
        df_details = read_xls_details(xls_details)

        # Add details from df_details
        df = df_uv.merge(df_details, how='left',
                         left_on='Intervenants',
                         right_on='Intervenants')

        dfs = df.sort_values(['Responsable', 'Statut', 'SortCourseList'],
                             ascending=False)
        dfs = dfs.reset_index()

        insts = []
        for _, row in dfs.iterrows():
            insts.append({
                'inst': row['Intervenants'],
                'libss': row['CourseList'],
                'resp': row['Responsable'],
                'website': row['Website'],
                'email': row['Email']
            })

        def contact(info):
            if not pd.isnull(info['website']):
                return f'[{info["inst"]}]({info["website"]})'
            elif not pd.isnull(info['email']):
                return f'[{info["inst"]}](mailto:{info["email"]})'
            else:
                return info['inst']

        env = jinja2.Environment(loader=jinja2.FileSystemLoader('documents/'))
        # env.globals.update(contact=contact)
        template = env.get_template('instructors.html.jinja2')
        md = template.render(insts=insts, contact=contact)
        html = markdown.markdown(md)

        with open(target, 'w') as fd:
            fd.write(html)

    for uv in CONFIG['UV']:
        insts_uv = f'documents/{uv}_intervenants_rempli.xlsx'
        insts_details = f'documents/intervenants.xlsx'
        target = f'generated/{uv}_intervenants.html'
        yield {
            'name': uv,
            'file_dep': [insts_uv, 'documents/instructors.html.jinja2'],
            'targets': [target],
            'actions': [(html_inst, [insts_uv, insts_details, target])],
            'verbosity': 2
        }


def task_cal_inst():
    """Calendrier PDF par intervenants"""

    uv_list = 'generated/UTC_UV_list_instructors.csv'

    def create_cal_from_list(uv, uv_list_filename):
        df = pd.read_csv(uv_list_filename)
        if 'Intervenants' not in df.columns:
            raise Exception('Pas d\'enregistrement des intervenants')
        df_uv = df.loc[df['Code enseig.'] == uv, :]
        df_uv_real = df_uv.loc[df['Type créneau'] == 'Groupe actif', :]

        text = r'{name} \\ {room} \\ {author}'
        for instructor, group in df_uv_real.groupby(['Intervenants']):
            target = f'generated/{uv}_{instructor.replace(" ", "_")}_calendrier.pdf'
            create_cal_from_dataframe(group, text, target)

    for uv in CONFIG['UV']:
        yield {
            'name': uv,
            'file_dep': [uv_list, 'documents/calendar_template.tex.jinja2'],
            'actions': [(create_cal_from_list, [uv, uv_list])]
        }


def task_add_instructors():
    """Ajoute les intervenants dans la liste csv des créneaux"""

    def add_instructors(target, csv, *insts):
        df_csv = pd.read_csv(csv)

        df_insts = [pd.read_excel(inst) for inst in insts]
        df_inst = pd.concat(df_insts, ignore_index=True)

        df_merge = pd.merge(df_csv, df_inst, how='left', on=['Jour', 'Heure début', 'Heure fin', 'Semaine', 'Lib. créneau', 'Locaux'])

        df_merge.to_csv(target, index=False)

    target = 'generated/UTC_UV_list_instructors.csv'
    deps = ['generated/UTC_UV_list.csv']
    for uv in CONFIG['UV']:
        if os.path.exists(f'documents/{uv}_intervenants_rempli.xlsx'):
            deps.append(f'documents/{uv}_intervenants_rempli.xlsx')

    return {
        'file_dep': deps,
        'targets': [target],
        'actions': [(add_instructors, [target] + deps)],
        'verbosity': 2
    }


def create_cal_from_dataframe(df, text, target):
    """Crée un calendrier avec text dans les cases"""

    # 08:15 should be 8_15
    def convert_time(time):
        time = time.replace(':', '_')
        return(re.sub('^0', '', time))

    def convert_day(day):
        mapping = {'Lundi': 'Lun',
                   'Mardi': 'Mar',
                   'Mercredi': 'Mer',
                   'Jeudi': 'Jeu',
                   'Vendredi': 'Ven',
                   'Samedi': 'Sam',
                   'Dimanche': 'Dim'}
        return(mapping[day])

    def convert_author(author):
        parts = re.split('[ -]', author)
        return(''.join(e[0].upper() for e in parts))

    # Returns blocks like \node[2hours, full, {course}] at ({day}-{bh}) {{{text}}};
    def build_block(row, text, half=False):
        uv = row['Code enseig.']

        name = row['Lib. créneau'].replace(' ', '')
        if re.match('^T', name):
            ctype = 'TP'
            name = name + row['Semaine']
        elif re.match('^D', name):
            ctype = 'TD'
        elif re.match('^C', name):
            ctype = 'Cours'

        if 'Intervenants' in row.keys():
            if pd.isnull(row['Intervenants']):
                author = 'N/A'
            else:
                author = convert_author(row['Intervenants'])
        else:
            author = 'N/A'

        room = row['Locaux']
        room = room.replace(' ', '').replace('BF', 'F')

        text = text.format(room=room, name=name, author=author)

        # if half:
        #     text = r"""
        #     \begin{fitbox}{1.4cm}{1.8cm}
        #     \begin{center}
        #     (((text)))
        #     \end{center}
        #     \end{fitbox}
        #     """.replace('(((text)))', text)

        bh = convert_time(row['Heure début'])
        day = convert_day(row['Jour'])

        if not half:
            half = 'full'
        return(rf'\node[2hours, {half}, {ctype}] at ({day}-{bh}) {{{text}}};')

    blocks = []
    for hour, group in df.groupby(['Jour', 'Heure début', 'Heure fin']):
        if len(group) > 2:
            raise Exception("Trop de créneaux en même temps")
        elif len(group) == 2:
            group = group.sort_values('Semaine')
            block1 = build_block(group.iloc[0], text, half='atleft')
            block2 = build_block(group.iloc[1], text, half='atright')
            blocks += [block1, block2]
            pass
        elif len(group) == 1:
            block = build_block(group.iloc[0], text)
            blocks.append(block)

    blocks = '\n'.join(blocks)

    latex_jinja_env = jinja2.Environment(
        block_start_string='((*',
        block_end_string='*))',
        variable_start_string='(((',
        variable_end_string=')))',
        comment_start_string='((=',
        comment_end_string='=))',
        loader=jinja2.FileSystemLoader('documents/')
    )

    template = latex_jinja_env.get_template('calendar_template.tex.jinja2')

    tex = template.render(blocks=blocks)

    # base = os.path.splitext(target)[0]
    # with open(base+'.tex', 'w') as fd:
    #     fd.write(tex)

    pdf = latex.build_pdf(tex)
    pdf.save_to(target)


def task_cal_uv():
    """Calendrier PDF global de l'UV.

Crée le calendrier des Cours/TD/TP de toutes les UV listées dans
CONFIG['UV'].
    """

    def create_cal_from_list(uv, uv_list_filename, target):
        df = pd.read_csv(uv_list_filename)

        # Filtre par uv 'Groupe actif' et intervenant existant
        df_uv = df.loc[df['Code enseig.'] == uv, :]
        df_uv_real = df_uv.loc[df['Type créneau'] == 'Groupe actif', :]
        df_uv_real = df_uv_real.loc[~pd.isnull(df['Intervenants']), :]

        text = r'{name} \\ {room} \\ {author}'
        return(create_cal_from_dataframe(df_uv_real, text, target))

    uv_list = 'generated/UTC_UV_list_instructors.csv'
    for uv in CONFIG['UV']:
        target = 'generated/' + uv + '_calendrier.pdf'
        yield {
            'name': uv,
            'file_dep': [uv_list, 'documents/calendar_template.tex.jinja2'],
            'targets': [target],
            'actions': [(create_cal_from_list, [uv, uv_list, target])]
        }


# def task_utc_listing_to_csv():
#     """Construit un fichier CSV à partir des données brutes de la promo
#     fournies par l'UTC."""

#     utc_listing = 'documents/SY02_P2018_INSCRITS.raw'

#     return {
#         'file_dep': [utc_listing],
#         'targets': ['generated/SY02_P2018_INSCRITS.csv'],
#         'actions': [['scripts/']]
#     }


# def task_merge_utc_moodle_csv():
#     """Construit un fichier CSV unique avec les informations de Moodle et
#     de l'UTC."""

#     moodle_listing = 'documents/SY02_P2018_MOODLE.csv'
#     utc_listing_csv = 'generated/SY02_P2018_INSCRITS.csv'
#     tiers_temps = 'documents/SY02_P2018_TIERS_TEMPS.lst'

#     return {
#         'file_dep': [moodle_listing, utc_listing_csv, tiers_temps],
#         'targets': ['generated/SY02_P2018_UTC_MOODLE_MERGE.csv'],
#         'actions': [['scripts/']]
#     }


def create_plannings():
    def skip_range(d1, d2):
        return([d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)])

    def skip_week(d1, weeks=1):
        return([d1 + timedelta(days=x) for x in range(7*weeks-1)])

    ferie = [date(2018, 4, 2),
             date(2018, 5, 1),
             date(2018, 5, 8),
             date(2018, 5, 10),
             date(2018, 5, 21)]

    debut = skip_week(date(2018, 2, 19))
    median = skip_range(date(2018, 5, 2), date(2018, 5, 9))

    semaine_su = skip_week(date(2018, 4, 16), weeks=2)

    turn = {
        date(2018, 5, 9): 'Mardi',
        date(2018, 5, 25): 'Lundi'
    }

    skip_days_C = ferie + semaine_su + median
    skip_days_D = ferie + semaine_su + debut + median
    skip_days_T = ferie + semaine_su + debut

    beg = CONFIG['PL_BEG']
    end = CONFIG['PL_END']

    def generate_days(beg, end, skip, turn, course):
        daynames = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
        days = []
        delta = end - beg
        semaine = {'Lundi': 0, 'Mardi': 0, 'Mercredi': 0, 'Jeudi': 0, 'Vendredi': 0}

        nweek = 0
        for i in range(delta.days + 1):
            d = beg + timedelta(days=i)

            if i % 7 == 0:
                nweek += 1

            if d.weekday() in [5, 6]:
                continue

            if d in skip:
                continue

            if d in turn:
                day = turn[d]
            else:
                day = daynames[d.weekday()]

            if course == 'T':
                if semaine[day] % 2 == 0:
                    sem = 'A'
                else:
                    sem = 'B'
                num = semaine[day] // 2 + 1
                semaine[day] += 1
            elif course in ['C', 'D']:
                semaine[day] += 1
                sem = None
                num = semaine[day]
            else:
                raise Exception("course inconnu")

            if d in turn:
                days.append((d, turn[d], sem, num, nweek))
            else:
                days.append((d, daynames[d.weekday()], sem, num, nweek))

        return(days)

    planning_C = generate_days(beg, end, skip_days_C, turn, 'C')
    planning_D = generate_days(beg, end, skip_days_D, turn, 'D')
    planning_T = generate_days(beg, end, skip_days_T, turn, 'T')

    return({
        'C': planning_C,
        'D': planning_D,
        'T': planning_T
    })


def task_ical_inst():
    """Create iCal file for each instructor"""

    deps = ['generated/UTC_UV_list_instructors.csv']

    def create_ical_inst(csv):
        df = pd.read_csv(csv)
        df = df.loc[~pd.isnull(df['Intervenants']), :]

        planning = create_plannings()

        planning_C = planning['C']
        pl_C = pd.DataFrame(planning_C)
        pl_C.columns = ['date', 'dayname', 'semaine', 'num', 'nweek']

        df_C = df.loc[df['Lib. créneau'].str.startswith('C'), :]
        df_Cm = pd.merge(df_C, pl_C, how='left', left_on='Jour', right_on='dayname')

        planning_D = planning['D']
        pl_D = pd.DataFrame(planning_D)
        pl_D.columns = ['date', 'dayname', 'semaine', 'num', 'nweek']

        df_D = df.loc[df['Lib. créneau'].str.startswith('D'), :]
        df_Dm = pd.merge(df_D, pl_D, how='left', left_on='Jour', right_on='dayname')

        planning_T = planning['T']
        pl_T = pd.DataFrame(planning_T)
        pl_T.columns = ['date', 'dayname', 'semaine', 'num', 'nweek']

        df_T = df.loc[df['Lib. créneau'].str.startswith('T'), :]
        df_Tm = pd.merge(df_T, pl_T, how='left', left_on=['Jour', 'Semaine'], right_on=['dayname', 'semaine'])

        dfm = pd.concat([df_Cm, df_Dm, df_Tm], ignore_index=True)

        for inst, group in dfm.groupby('Intervenants'):
            output = f'generated/{inst.replace(" ", "_")}.ics'
            write_ical_file(group, output)

    return {
        'file_dep': ['generated/UTC_UV_list_instructors.csv'],
        'actions': [(create_ical_inst, deps)]
    }


def task_csv_all_courses():
    "Fichier csv de tous les créneaux du semestre"

    def csv_all_courses(csv, target):
        df = pd.read_csv(csv)
        df = df.loc[df['Code enseig.'].isin(CONFIG['UV'])]

        planning = create_plannings()

        planning_C = planning['C']
        pl_C = pd.DataFrame(planning_C)
        pl_C.columns = ['date', 'dayname', 'semaine', 'num', 'nweek']

        df_C = df.loc[df['Lib. créneau'].str.startswith('C'), :]
        df_Cm = pd.merge(df_C, pl_C, how='left', left_on='Jour', right_on='dayname')

        planning_D = planning['D']
        pl_D = pd.DataFrame(planning_D)
        pl_D.columns = ['date', 'dayname', 'semaine', 'num', 'nweek']

        df_D = df.loc[df['Lib. créneau'].str.startswith('D'), :]
        df_Dm = pd.merge(df_D, pl_D, how='left', left_on='Jour', right_on='dayname')

        planning_T = planning['T']
        pl_T = pd.DataFrame(planning_T)
        pl_T.columns = ['date', 'dayname', 'semaine', 'num', 'nweek']

        df_T = df.loc[df['Lib. créneau'].str.startswith('T'), :]
        df_Tm = pd.merge(df_T, pl_T, how='left', left_on=['Jour', 'Semaine'], right_on=['dayname', 'semaine'])

        dfm = pd.concat([df_Cm, df_Dm, df_Tm], ignore_index=True)
        dfm.to_csv(target, index=False)

    dep = 'generated/UTC_UV_list_instructors.csv'
    target = 'generated/UTC_UV_list_créneau.csv'

    return {
        'file_dep': [dep],
        'actions': [(csv_all_courses, [dep, target])],
        'targets': [target]
    }


def write_ical_file(dataframe, output):

    def timestamp(row):
        d = row['date']
        hm = row['Heure début'].split(':')
        h = int(hm[0])
        m = int(hm[1])
        return(datetime(year=d.year, month=d.month, day=d.day, hour=h, minute=m))

    ts = dataframe.apply(timestamp, axis=1)
    dataframe.is_copy = False   # SettingWithCopyWarning
    dataframe['timestamp'] = ts
    df = dataframe.sort_values('timestamp')

    cal = Calendar()
    cal['summary'] = CONFIG['SEMESTER']

    for uv, group in df.groupby('Code enseig.'):
        for index, row in group.iterrows():
            event = Event()

            name = row['Lib. créneau'].replace(' ', '')
            week = row['Semaine']

            if re.match('^T', name):
                name = name + row['Semaine']

            room = row['Locaux'].replace(' ', '').replace('BF', 'F')
            num = row['num']
            activity = row['Activité']

            if activity == 'TP':
                summary = f'{uv} {activity}{num} {week} {room}'
            else:
                summary = f'{uv} {activity}{num} {room}'

            event.add('summary', summary)

            dt = row['timestamp']
            event.add('dtstart', dt)
            event.add('dtend', dt + timedelta(hours=2))

            cal.add_component(event)

    with open(output, 'wb') as fd:
        fd.write(cal.to_ical(sorted=True))


def task_compute_plannings():
    return {'actions': [create_plannings]}


def task_html_table():
    """Table HTML des TD/TP"""

    def html_table(**kwargs):
        uv = kwargs['uv']
        course = kwargs['course']
        slots = kwargs['slots']

        # Select wanted slots
        slots = slots.loc[slots['Code enseig.'] == uv, :]
        slots = slots.loc[slots['Activité'] == course, :]

        # Return if no slots
        if len(slots) == 0:
            print("Pas de créneau")
            return

        # Merge when multiple slots on same week
        if course == 'TP':
            lb = lambda df: ', '.join(df.semaine + df.num.apply(str))
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
        for (mon, nmon) in mondays(CONFIG['PL_BEG'], CONFIG['PL_END']):
            weeks.append('{}-{}'.format(mon.strftime('%d/%m'),
                                        (nmon-timedelta(days=1)).strftime('%d/%m')))
            cr_week = slots.loc[(slots.date >= mon) & (slots.date < nmon)]

            if len(cr_week) > 0:
                e = cr_week.groupby('Lib. créneau').apply(lb)
                rows.append(e)
            else:
                rows.append(pd.Series())

        # Weeks on rows
        df = pd.concat(rows, axis=1).transpose()

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

        with open(f'generated/{uv}_{course}_table.html', 'w') as fd:
            fd.write(output)

    for course, short in [('TD', 'D'), ('TP', 'T'), ('Cours', 'C')]:
        for uv in CONFIG['UV']:
            yield {
                'name': f'{uv}{course}',
                'actions': [(html_table, [], {'uv': uv, 'course': course})],
                'getargs': {'slots': ('compute_slots', 'slots')},
                'targets': [f'generated/{uv}_{course}_table.html'],
                'verbosity': 2
            }


def task_compute_slots():
    def compute_slots(**kwargs):
        planning = kwargs['planning']
        print(planning)
        csv_inst_list = kwargs['csv']

        df = pd.read_csv(csv_inst_list)
        df = df.loc[~pd.isnull(df['Intervenants']), :]

        planning_C = planning['C']
        pl_C = pd.DataFrame(planning_C)
        pl_C.columns = ['date', 'dayname', 'semaine', 'num', 'nweek']

        df_C = df.loc[df['Activité'] == 'Cours', :]
        df_Cm = pd.merge(df_C, pl_C, how='left', left_on='Jour', right_on='dayname')

        planning_D = planning['D']
        pl_D = pd.DataFrame(planning_D)
        pl_D.columns = ['date', 'dayname', 'semaine', 'num', 'nweek']

        df_D = df.loc[df['Activité'] == 'TD', :]
        df_Dm = pd.merge(df_D, pl_D, how='left', left_on='Jour', right_on='dayname')

        planning_T = planning['T']
        pl_T = pd.DataFrame(planning_T)
        pl_T.columns = ['date', 'dayname', 'semaine', 'num', 'nweek']

        df_T = df.loc[df['Activité'] == 'TP', :]
        df_Tm = pd.merge(df_T, pl_T, how='left', left_on=['Jour', 'Semaine'], right_on=['dayname', 'semaine'])

        dfm = pd.concat([df_Cm, df_Dm, df_Tm], ignore_index=True)

        return({'slots': dfm})

    dep = 'generated/UTC_UV_list_instructors.csv'

    return {
        'file_dep': [dep],
        'actions': [(compute_slots, [], {'csv': dep})],
        'getargs': {'planning': ('compute_plannings', None)},
        'verbosity': 2
    }


def task_restriction_list():
    """Ficher json des restrictions d'accès des TP"""

    sys.path.append('scripts/')
    from moodle_date import CondDate, CondGroup, CondOr

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
                    group = row['Lib. créneau'] + row['Semaine']
                    dt = (datetime.strptime(row['date'], DATE_FORMAT).date() +
                          timedelta(days=1))
                    sts.append((CondGroup() == group) & (CondDate() >= dt))

                return (num, {'enonce': (CondDate() >= dt_min).to_PHP(),
                              'corrige': CondOr(sts=sts).to_PHP()})

            else:               # Dispo après la dernière séance
                dt_min = pd.to_datetime(df['date']).min().date()
                dt_max = pd.to_datetime(df['date']).max().date()
                return (num, {'enonce': (CondDate() >= dt_min).to_PHP(),
                              'corrige': (CondDate() >= dt_max).to_PHP()})

        gb = df.groupby('num')
        moodle_date = dict([get_beg_end_date_each(name, g) for name, g in gb
                            if get_beg_end_date_each(name, g) is not None])
        with open('generated/moodle_date.json', 'w') as fd:
            json.dump(moodle_date, fd, indent=4)

    dep = 'generated/UTC_UV_list_créneau.csv'

    uv = 'SY02'
    target = ''
    return {
        'actions': [(restriction_list, [uv, dep, target])],
        'file_dep': [dep],
        'verbosity': 2
    }
