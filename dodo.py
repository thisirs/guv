import os
import glob
import sys
from shutil import copyfile
import tempfile
import zipfile
import re
import random
import time
from datetime import datetime, date, timedelta
import math
import json
import asyncio
import aiohttp
import hashlib
import pynliner
import markdown
import numpy as np
import pandas as pd
from pandas.api.types import CategoricalDtype
from icalendar import Event, Calendar
from PyPDF2 import PdfFileReader
from tabula import read_pdf
import latex
import jinja2
import oyaml as yaml            # Ordered yaml

from doit import get_var
from doit.exceptions import TaskError, TaskFailed

# Documents communs à toutes les UVs et spécifiques du semestre
COMMON_DOC = 'documents/'

# Documents générés non destinés à être modifiés manuellement
GENERATED = '{uv or ue}/generated/'

# Documents générés prêts à être utilisés
DOCUMENTS = '{uv or ue}/documents/'


DOIT_CONFIG = {'default_tasks': [
    'xls_student_data_merge',
    'utc_uv_list_to_csv'
],
               'verbosity': 2}

def effify(non_f_str: str, locals=None):
    return eval(f'f"""{non_f_str}"""', None, locals)


def common_doc(template, **info):
    fn = effify(template, **info)
    dn = effify(COMMON_DOC, **info)
    return os.path.join(dn, fn)


def generated(template, **info):
    if 'uv' in info or 'ue' in info:
        dn = os.path.join(GENERATED, template)
    else:
        dn = os.path.join(COMMON_DOC, template)

    return effify(dn, locals=info)


def documents(template, **info):
    if 'uv' in info or 'ue' in info:
        dn = os.path.join(DOCUMENTS, template)
    else:
        dn = os.path.join(COMMON_DOC, template)

    return effify(dn, locals=info)


def add_templates(**templates):
    def decorator(func):
        for key, value in templates.items():
            setattr(func, key, value)
        return func
    return decorator


@add_templates(target='inscrits.raw')
def task_inscrits():
    def inscrits(doc):
        if not os.path.exists(doc):
            return TaskFailed(f"Pas de fichier `{doc}'")
        else:
            print(f"Utilisation du fichier `{doc}'")

    for planning, uv, info in selected_uv():
        doc = documents(task_inscrits.target, **info)
        yield {
            'name': f'{planning}_{uv}',
            'actions': [(inscrits, [doc])],
            'targets': [doc],
            'uptodate': [True]
        }


@add_templates(target='creneaux-UV-prov_P19.pdf')
def task_UTC_UV_list():
    doc = common_doc(task_UTC_UV_list.target)

    def UTC_UV_list(doc):
        if not os.path.exists(doc):
            return TaskFailed(f"Pas de fichier `{doc}'")

    return {
        'actions': [(UTC_UV_list, [doc])],
        'targets': [doc]
    }


@add_templates(target='intervenants.xlsx')
def task_xls_instructors():
    doc = common_doc(task_xls_instructors.target)

    def xls_instructors(doc):
        if not os.path.exists(doc):
            return TaskFailed(f"Pas de fichier `{doc}'")

    return {
        'actions': [(xls_instructors, [doc])],
        'targets': [doc]
    }


def selected_uv(all=None):
    uvs = get_var('uv', '').split()
    plannings = get_var('planning', '').split()

    if all:
        uvs = plannings = []

    yield from selected_uv0(plannings, uvs)


def selected_uv0(plannings, uvs):
    if not plannings and not uvs:
        plannings = CONFIG['DEFAULT_PLANNINGS']

    for pl in CONFIG['ALL_PLANNINGS']:
        uvp = (CONFIG['PLANNING'][pl].get('UV') or
               CONFIG['PLANNING'][pl].get('UE'))
        if pl in plannings:
            for uv in uvp:
                yield pl, uv, {'planning': pl, 'uv': uv}
        else:
            for uv in uvs:
                if uv in uvp:
                    yield pl, uv, {'planning': pl, 'uv': uv}


def action_msg(msg, name=None):
    action = {
        'actions': [lambda: print(msg)],
        'verbosity': 2,
        'uptodate': [False]
    }
    if name:
        action['name'] = name

    return action


class KeepError(Exception):
    pass

class Output():
    def __init__(self, target, protected=False):
        self.target = target
        self.protected = protected

    def __enter__(self):
        if os.path.exists(self.target):
            if self.protected:
                while True:
                    try:
                        choice = input('Le fichier `%s'' existe déjà. Écraser (d), garder (g), sauvegarder (s), annuler (a) ? ' % self.target)
                        if choice == 'd':
                            os.remove(self.target)
                        elif choice == 's':
                            parts = os.path.splitext(self.target)
                            timestr = time.strftime("_%Y%m%d-%H%M%S")
                            target0 = parts[0] + timestr + parts[1]
                            os.rename(self.target, target0)
                        elif choice == 'g':
                            return lambda: 1/0
                        elif choice == 'a':
                            raise Exception('Annulation')
                        else:
                            raise ValueError
                    except ValueError:
                        continue
                    else:
                        break
            else:
                print('Écrasement du fichier `%s''' % self.target)
        else:
            dirname = os.path.dirname(self.target)
            if not os.path.exists(dirname):
                os.makedirs(dirname)

        return lambda: self.target

    def __exit__(self, type, value, traceback):
        if type is ZeroDivisionError:
            return True
        if type is None:
            print(f"Wrote `{self.target}'")


DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"
URL = 'https://demeter.utc.fr/portal/pls/portal30/portal30.get_photo_utilisateur?username='

LATEX_SUBS = (
    (re.compile(r'\\'), r'\\textbackslash'),
    (re.compile(r'([{}_#%&$])'), r'\\\1'),
    (re.compile(r'~'), r'\~{}'),
    (re.compile(r'\^'), r'\^{}'),
    (re.compile(r'"'), r"''"),
    (re.compile(r'\.\.\.+'), r'\\ldots'))


def escape_tex(value):
    newval = value
    for pattern, replacement in LATEX_SUBS:
        newval = pattern.sub(replacement, newval)
    return newval


# def object_hook(obj):
#     if '_type' not in obj:
#         return obj
#     type = obj['_type']
#     if type == 'datetime':
#         return datetime.strptime(obj['value'],
#                                  DATE_FORMAT + ' ' + TIME_FORMAT)
#     elif type == 'date':
#         return datetime.strptime(obj['value'], DATE_FORMAT).date()
#     elif type == 'DataFrame':
#         return pd.read_json(obj['value'])
#     return obj


# json._default_decoder = json.JSONDecoder(
#     object_pairs_hook=None,
#     object_hook=object_hook)


# def json_encoder_default(self, obj):
#     if isinstance(obj, pd.DataFrame):
#         return {
#             "_type": "DataFrame",
#             "value": obj.to_json()
#         }
#     elif isinstance(obj, datetime):
#         return {
#             "_type": "datetime",
#             "value": obj.strftime("%s %s" % (
#                 DATE_FORMAT, TIME_FORMAT
#             ))
#         }
#     elif isinstance(obj, date):
#         return {
#             "_type": "date",
#             "value": obj.strftime(DATE_FORMAT)
#         }
#     return json.JSONEncoder.default(self, obj)


# json.JSONEncoder.default = json_encoder_default


CONFIG = {
    'UV': ['SY02', 'SY09'],
    'DEFAULT_UV': 'SY02',
    'DEFAULT_INSTRUCTOR': 'Sylvain Rousseau',
    'DEFAULT_SEMESTER': 'A2018',
    'DEFAULT_PLANNING': 'A2018',
    'DEFAULT_PLANNINGS': ['A2018', '2018_T1', '2018_T2'],
    'PLANNING': {
        'P2018': {
            'UV': ['SY02', 'SY09'],
            'PL_BEG': date(2018, 2, 19),
            'PL_END': date(2018, 6, 22)
        },
        'A2018': {
            'UV': ['SY02', 'SY19'],
            'PL_BEG': date(2018, 9, 10),
            'PL_END': date(2019, 1, 10)
        },
        '2018_T1': {
            'UE': ['AOS1'],
            'PL_BEG': date(2018, 9, 10),
            'PL_END': date(2018, 11, 5)
        },
        '2018_T2': {
            'UE': ['AOS2'],
            'PL_BEG': date(2018, 11, 13),
            'PL_END': date(2019, 1, 10)
        },
        'P2019': {
            'UV': ['SY02', 'SY09'],
            'PL_BEG': date(2019, 2, 25),
            'PL_END': date(2019, 6, 29)
        }
    }
}


def read_xls_details(fn):
    """Lit un fichier Excel avec un ordre sur la colonne 'Statut'."""

    sts = ['MCF', 'PR', 'PRAG', 'PRCE', 'PAST', 'ECC', 'Doct', 'ATER',
           'Vacataire']
    status_type = CategoricalDtype(categories=sts, ordered=True)

    return pd.read_excel(fn, dtype={
        'Statut': status_type
    })


@add_templates(target='intervenants_details.xlsx')
def task_xls_inst_details():
    """Fichier Excel des intervenants par UV avec détails"""

    def xls_inst_details(inst_uv, inst_details, target):
        inst_uv = pd.read_excel(inst_uv)
        inst_details = pd.read_excel(inst_details)

        # Add details from inst_details
        df = inst_uv.merge(inst_details, how='left',
                           left_on='Intervenants',
                           right_on='Intervenants')

        with Output(target) as target:
            df.to_excel(target(), index=False)

    insts_details = common_doc(task_xls_instructors.target)

    for planning, uv, info in selected_uv():
        inst_uv = documents(task_xls_affectation.target, **info)
        target = generated(task_xls_inst_details.target, **info)
        yield {
            'name': f'{planning}_{uv}',
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


@add_templates(
    target='remplacement.xlsx'
)
def task_xls_UTP():
    """Crée un document Excel pour calcul des heures et remplacements."""

    sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts/'))
    from excel_hours import create_excel_file

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

    insts = common_doc(task_xls_instructors.target)
    for planning, uv, info in selected_uv():
        xls = documents(task_xls_affectation.target, **info)
        target = generated(task_xls_UTP.target, **info)

        yield {
            'name': f'{planning}_{uv}',
            'file_dep': [xls, insts],
            'targets': [target],
            'actions': [(xls_UTP, [xls, insts, target])],
            'verbosity': 2
        }


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
        uvs = CONFIG['PLANNING'][CONFIG['DEFAULT_SEMESTER']]['UV']
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

    uv_list_filename = common_doc(task_UTC_UV_list.target)
    ue_list_filename = common_doc('UTC_UE_list.xlsx')
    target = common_doc(task_utc_uv_list_to_csv.target)

    deps = [uv_list_filename]
    if os.path.exists(ue_list_filename):
        deps.append(ue_list_filename)

    semester = CONFIG['DEFAULT_SEMESTER']
    return {
        'file_dep': deps,
        'targets': [target],
        'actions': [(utc_uv_list_to_csv, [semester, uv_list_filename, ue_list_filename, target])],
        'verbosity': 2
    }


@add_templates(target='intervenants.xlsx')
def task_xls_affectation():
    """Fichier Excel des créneaux de toutes les UV configurées."""

    def extract_uv_instructor(uv_list_filename, uv, target):
        df = pd.read_csv(uv_list_filename)
        df_uv = df.loc[df['Code enseig.'] == uv, :]

        selected_columns = ['Jour', 'Heure début', 'Heure fin', 'Locaux',
                            'Semaine', 'Lib. créneau']
        df_uv = df_uv[selected_columns]
        df_uv['Intervenants'] = ''
        df_uv['Responsable'] = ''

        # Copy for modifications
        with Output(target, protected=True) as target:
            df_uv.to_excel(target(), sheet_name='Intervenants', index=False)

    for planning, uv, info in selected_uv():
        uvlist_csv = common_doc(task_utc_uv_list_to_csv.target)
        target = documents(task_xls_affectation.target, **info)

        yield {
            'name': f'{planning}_{uv}',
            'file_dep': [uvlist_csv],
            'targets': [target],
            'actions': [(extract_uv_instructor, [uvlist_csv, uv, target])],
            'verbosity': 2
        }


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
        dep = documents(task_xls_affectation.target, **info)
        target = generated(task_xls_emploi_du_temps.target, **info)
        yield {
            'name': f'{planning}_{uv}',
            'file_dep': [dep],
            'targets': [target],
            'actions': [(xls_emploi_du_temps, [dep, target])],
            'verbosity': 2
        }


@add_templates(target='intervenants.html')
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

        jinja_dir = os.path.join(os.path.dirname(__file__), 'templates')
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(jinja_dir))
        # env.globals.update(contact=contact)
        template = env.get_template('instructors.html.jinja2')
        md = template.render(insts=insts, contact=contact)
        html = markdown.markdown(md)

        with Output(target) as target:
            with open(target(), 'w') as fd:
                fd.write(html)

    insts_details = documents('intervenants.xlsx')
    jinja_dir = os.path.join(os.path.dirname(__file__), 'templates')
    template = os.path.join(jinja_dir, 'instructors.html.jinja2')

    for planning, uv, info in selected_uv():
        insts_uv = documents(task_xls_affectation.target, **info)
        target = generated(task_html_inst.target, **info)

        yield {
            'name': f'{planning}_{uv}',
            'file_dep': [insts_uv, insts_details, template],
            'targets': [target],
            'actions': [(html_inst, [insts_uv, insts_details, target])],
            'verbosity': 2
        }


def task_cal_inst():
    """Calendrier PDF d'une semaine de toutes les UV/UE d'un intervenant."""

    uv_list = generated(task_add_instructors.target)

    def create_cal_from_list(inst, plannings, uv_list_filename, target):
        df = pd.read_csv(uv_list_filename)
        if 'Intervenants' not in df.columns:
            raise Exception('Pas d\'enregistrement des intervenants')

        df_inst = df.loc[(df['Intervenants'].astype(str) == inst) &
                         (df['Planning'].isin(plannings)), :]
        text = r'{uv} \\ {name} \\ {room}'
        create_cal_from_dataframe(df_inst, text, target)

    plannings = get_var('planning', '').split() or CONFIG['DEFAULT_PLANNINGS']
    insts = get_var('insts', '').split() or [CONFIG['DEFAULT_INSTRUCTOR']]
    for inst in insts:
        target = generated(f'{inst.replace(" ", "_")}_{"_".join(plannings)}_calendrier.pdf')
        jinja_dir = os.path.join(os.path.dirname(__file__), 'templates')

        yield {
            'name': '_'.join(plannings) + '_' + inst,
            'targets': [target],
            'file_dep': [uv_list, os.path.join(jinja_dir, 'calendar_template.tex.jinja2')],
            'actions': [(create_cal_from_list, [inst, plannings, uv_list, target])],
            'verbosity': 2
        }


@add_templates(target='UTC_UV_list_instructors.csv')
def task_add_instructors():
    """Ajoute les intervenants dans la liste csv des créneaux"""

    def add_instructors(target, csv, insts):
        df_csv = pd.read_csv(csv)

        df_insts = [pd.read_excel(inst) for inst in insts]
        df_inst = pd.concat(df_insts, ignore_index=True)
        df_inst.Semaine = df_inst.Semaine.astype(object)

        df_merge = pd.merge(df_csv, df_inst, how='left', on=['Jour', 'Heure début', 'Heure fin', 'Semaine', 'Lib. créneau', 'Locaux'])

        with Output(target) as target:
            df_merge.to_csv(target(), index=False)

    target = generated(task_add_instructors.target)
    uv_list = common_doc(task_utc_uv_list_to_csv.target)
    insts = []
    for planning, uv, info in selected_uv('all'):
        insts.append(documents(task_xls_affectation.target, **info))

    deps = insts + [uv_list]

    return {
        'file_dep': deps,
        'targets': [target],
        'actions': [(add_instructors, [target, uv_list, insts])],
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
            if isinstance(row['Semaine'], str):
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

        text = text.format(room=room, name=name, author=author, uv=uv)

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

    jinja_dir = os.path.join(os.path.dirname(__file__), 'templates')
    latex_jinja_env = jinja2.Environment(
        block_start_string='((*',
        block_end_string='*))',
        variable_start_string='(((',
        variable_end_string=')))',
        comment_start_string='((=',
        comment_end_string='=))',
        loader=jinja2.FileSystemLoader(jinja_dir)
    )

    template = latex_jinja_env.get_template('calendar_template.tex.jinja2')

    tex = template.render(blocks=blocks)

    # base = os.path.splitext(target)[0]
    # with open(base+'.tex', 'w') as fd:
    #     fd.write(tex)

    pdf = latex.build_pdf(tex)

    with Output(target) as target:
        pdf.save_to(target())


@add_templates(target='calendrier.pdf')
def task_cal_uv():
    """Calendrier PDF global de l'UV.

Crée le calendrier des Cours/TD/TP de toutes les UV listées dans
CONFIG['UV'].
    """

    def create_cal_from_list(uv, uv_list_filename, target):
        df = pd.read_excel(uv_list_filename)
        # df_uv_real = df.loc[~pd.isnull(df['Intervenants']), :]
        df_uv_real = df
        df_uv_real['Code enseig.'] = uv

        text = r'{name} \\ {room} \\ {author}'
        return(create_cal_from_dataframe(df_uv_real, text, target))

    jinja_dir = os.path.join(os.path.dirname(__file__), 'templates')
    template = os.path.join(jinja_dir, 'calendar_template.tex.jinja2')

    for planning, uv, info in selected_uv():
        uv_list = documents(task_xls_affectation.target, **info)
        target = generated(task_cal_uv.target, **info)

        yield {
            'name': f'{planning}_{uv}',
            'file_dep': [uv_list, template],
            'targets': [target],
            'actions': [(create_cal_from_list, [uv, uv_list, target])]
        }


@add_templates(target='inscrits.csv')
def task_csv_inscrits():
    """Construit un fichier CSV à partir des données brutes de la promo
    fournies par l'UTC."""

    sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts/'))
    from parse_utc_list import parse_UTC_listing

    def csv_inscrits(fn, target):
        df = parse_UTC_listing(fn)
        with Output(target) as target:
            df.to_csv(target(), index=False)

    for planning, uv, info in selected_uv():
        utc_listing = documents(task_inscrits.target, **info)
        target = generated(task_csv_inscrits.target, **info)
        yield {
            'name': f'{planning}_{uv}',
            'file_dep': [utc_listing],
            'targets': [target],
            'actions': [(csv_inscrits, [utc_listing, target])],
            'verbosity': 2
        }


@add_templates(target='student_data.xlsx')
def task_xls_student_data():
    """Fusionne les informations sur les étudiants fournies par Moodle et
l'UTC."""

    def merge_student_data(target, **kw):
        sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts/'))
        from add_student_data import (add_moodle_data,
                                      add_UTC_data,
                                      add_tiers_temps,
                                      add_switches)

        if 'extraction_ENT' in kw:
            df = pd.read_excel(kw['extraction_ENT'])
            if 'csv_moodle' in kw:
                df = add_moodle_data(df, kw['csv_moodle'])

            if 'csv_UTC' in kw:
                df = add_UTC_data(df, kw['csv_UTC'])
        elif 'csv_UTC' in kw:
            df = pd.read_csv(kw['csv_UTC'])
            if 'csv_moodle' in kw:
                df = add_moodle_data(df, kw['csv_moodle'])
        elif 'csv_moodle' in kw:
            df = pd.read_csv(kw['csv_moodle'])

        if 'tiers_temps' in kw:
            df = add_tiers_temps(df, kw['tiers_temps'])

        if 'TD_switches' in kw:
            df = add_switches(df, kw['TD_switches'], 'TD')

        if 'TP_switches' in kw:
            df = add_switches(df, kw['TP_switches'], 'TP')

        dff = df.sort_values(['Nom', 'Prénom'])

        with Output(target) as target:
            dff.to_excel(target(), index=False)

    for planning, uv, info in selected_uv():
        kw = {}
        deps = []

        extraction_ENT = documents('extraction_enseig_note.xlsx', **info)
        if os.path.exists(extraction_ENT):
            kw['extraction_ENT'] = extraction_ENT
            deps.append(extraction_ENT)

        csv_moodle = documents('inscrits_moodle.csv', **info)
        if os.path.exists(csv_moodle):
            kw['csv_moodle'] = csv_moodle
            deps.append(csv_moodle)

        csv_UTC = generated(task_csv_inscrits.target, **info)
        raw_UTC = documents(task_inscrits.target, **info)
        if os.path.exists(raw_UTC):
            kw['csv_UTC'] = csv_UTC
            deps.append(csv_UTC)

        tiers_temps = documents('tiers_temps.raw', **info)
        if os.path.exists(tiers_temps):
            kw['tiers_temps'] = tiers_temps
            deps.append(tiers_temps)

        TD_switches = documents('TD_switches.raw', **info)
        if os.path.exists(TD_switches):
            kw['TD_switches'] = TD_switches
            deps.append(TD_switches)

        TP_switches = documents('TP_switches.raw', **info)
        if os.path.exists(TP_switches):
            kw['TP_switches'] = TP_switches
            deps.append(TP_switches)

        target = generated(task_xls_student_data.target, **info)

        if deps:
            yield {
                'name': f'{planning}_{uv}',
                'file_dep': deps,
                'targets': [target],
                'actions': [(merge_student_data, [target], kw)],
                'verbosity': 2
            }
        else:
            yield action_msg("Pas de données étudiants", name=f'{planning}_{uv}')


@add_templates(target='student_data_merge.xlsx')
def task_xls_student_data_merge():
    """Ajoute toutes les autres informations étudiants"""

    def merge_student_data(source, target, data):
        df = pd.read_excel(source)

        for path, agregater in data.items():
            print('Agregating %s' % path)
            df = agregater(df, path)

        dff = df.sort_values(['Nom', 'Prénom'])

        with Output(target) as target0:
            dff.to_excel(target0(), index=False)

        target = os.path.splitext(target)[0] + '.csv'
        with Output(target) as target:
            dff.to_csv(target(), index=False)

    def agregate(left_on, right_on, subset=None, drop=None, rename=None, read_method=None, kw_read={}):
        def agregate0(df, path):
            if left_on not in df.columns:
                raise Exception("Pas de colonne %s dans le dataframe", left_on)
            if read_method is None:
                if path.endswith('.csv'):
                    dff = pd.read_csv(path, **kw_read)
                elif path.endswith('.xlsx'):
                    dff = pd.read_excel(path, **kw_read)
                else:
                    raise Exception('No read method and unsupported file extension')
            else:
                dff = read_method(path, **kw_read)

            if subset is not None:
                dff = dff[list(set([right_on] + subset))]
            if drop is not None:
                if right_on in drop:
                    raise Exception('On enlève pas la clé')
                dff = dff.drop(drop, axis=1, errors='ignore')
            if rename is not None:
                if right_on in rename:
                    raise Exception('Pas de renommage de la clé possible')
                dff = dff.rename(columns=rename)
            if right_on not in dff.columns:
                raise Exception("Pas de colonne %s dans le dataframe", right_on)
            df = df.merge(dff, left_on=left_on, right_on=right_on, suffixes=('', '_y'))
            drop_cols = [right_on + '_y']
            df = df.drop(drop_cols, axis=1, errors='ignore')
            return df
        return agregate0

    for planning, uv, info in selected_uv():
        data = {}

        # Ajout des feuilles Excel de notes générées par xls_grades_sheet
        # for file in os.listdir('documents/'):
        #     m = re.match(rf"{planning}_{uv}_([^_]+)_gradebook.xlsx", file)
        #     if m:
        #         data['documents/' + file] = agregate(
        #             left_on='Courriel',
        #             right_on='Courriel',
        #             subset=['Note']
        #         )

        if uv == 'SY02':
            # Ajout des demi-groupes de TP pour examen
            data[generated('{planning}_{uv}_exam_groups.csv', **info)] = agregate(
                left_on='Courriel',
                right_on='Adresse de courriel')

            # Ajout de la note de médian si existant
            data[documents('{planning}_{uv}_median_notes.xlsx', **info)] = agregate(
                left_on='Courriel',
                right_on='Courriel',
                subset=['Note', 'Correcteur médian'],
                rename={'Note': 'Note médian'})

            # Ajout de la note de final si existant
            data[documents('{planning}_{uv}_final_notes.xlsx', **info)] = agregate(
                left_on='Courriel',
                right_on='Courriel',
                subset=['Note', 'Correcteur final'],
                rename={'Note': 'Note final'})

            # Ajout de la note globale
            data[documents('{planning}_{uv}_jury.xlsx', **info)] = agregate(
                left_on='Courriel',
                right_on='Courriel',
                subset=['Note'])

            # Ajout de la note de TP
            data[documents('SY02 Notes-20180614_1702-comma_separated.csv', **info)] = agregate(
                left_on='Courriel',
                right_on='Adresse de courriel',
                kw_read={'na_values': ['-']},
                subset=["Test Quiz P2018 (Brut)"],
                rename={"Test Quiz P2018 (Brut)": 'Note_TP'})
        elif uv == 'SY09':
            # Ajout des groupes de TP si existant
            data[generated('{planning}_{uv}_TD_P1_binomes.csv', **info)] = agregate(
                left_on='Courriel',
                right_on='Adresse de courriel',
                subset=['group'],
                rename={'group': 'group_P1'})

            data[generated('{planning}_{uv}_TD_P2_binomes.csv', **info)] = agregate(
                left_on='Courriel',
                right_on='Adresse de courriel',
                rename={'group': 'group_P2'})
        elif uv == 'SY19':
            # Ajout des binomes finaux du projet 1, exporté de Moodle
            data[documents('{planning}_{uv}_TD_P1_binomes_final.tsv', **info)] = agregate(
                left_on='Courriel',
                right_on='Adresse de courriel',
                subset=['Groupe'],
                rename={'Groupe': 'group_P1'},
                read_method=pd.read_csv,
                kw_read={'delimiter': '\t'})

            # Ajout des binomes finaux du projet 2, exporté de Moodle
            data[documents('{planning}_{uv}_TD_P2_binomes_final.tsv', **info)] = agregate(
                left_on='Courriel',
                right_on='Adresse de courriel',
                subset=['Groupe'],
                rename={'Groupe': 'group_P2'},
                read_method=pd.read_csv,
                kw_read={'delimiter': '\t'})

            # Ajout de la note de premier projet, TP3
            data[documents('A2018_SY19_TP3.xlsx', **info)] = agregate(
                left_on='Courriel',
                right_on='Adresse de courriel',
                subset=['Devoir TP 3 (Brut)'],
                rename={'Devoir TP 3 (Brut)': 'note_P1'})

            # Ajout de la note du QCM
            data[generated('A2018_SY19_QCM.csv', **info)] = agregate(
                left_on='Courriel',
                right_on='Courriel',
                drop=['Name'])

            # Ajout de la note examen hors QCM
            data[documents('A2018_SY19_final_gradebook.xlsx', **info)] = agregate(
                left_on='Courriel',
                right_on='Courriel',
                subset=['final'])

            # Ajout de la note du deuxième projet
            data[documents('A2018_SY19_P2_gradebook.xlsx', **info)] = agregate(
                left_on='Courriel',
                right_on='Courriel',
                subset=['P2'])

            # Ajout de la note du deuxième projet
            data[documents('A2018_SY19_jury_gradebook.xlsx', **info)] = agregate(
                left_on='Courriel',
                right_on='Courriel',
                subset=['Note ECTS'])

        elif uv == "AOS2":
            data[generated('2018_T2_AOS2_QCM.csv', **info)] = agregate(
                left_on='Courriel',
                drop=['Name'],
                right_on='Courriel',
                read_method=pd.read_csv)

            data[documents('2018_T2_AOS2_groups.tsv', **info)] = agregate(
                left_on='Courriel',
                right_on='Adresse de courriel',
                subset=['Groupe'],
                read_method=pd.read_csv,
                kw_read={'delimiter': '\t'})

            data[documents('2018_T2_AOS2_Project_gradebook.xlsx', **info)] = agregate(
                left_on='Courriel',
                right_on='Courriel',
                subset=['Project'])

            data[documents('2018_T2_AOS2_jury_gradebook.xlsx', **info)] = agregate(
                left_on='Courriel',
                right_on='Courriel',
                subset=['Note ECTS'])

        source = generated(task_xls_student_data.target, **info)

        target = generated(task_xls_student_data_merge.target, **info)
        deps = [source]
        data_exist = {}

        for path, agregater in data.items():
            if os.path.exists(path):
                deps.append(path)
                data_exist[path] = agregater

        yield {
            'name': f'{planning}_{uv}',
            'file_dep': deps,
            'targets': [target],
            'actions': [(merge_student_data, [source, target, data_exist])],
            'verbosity': 2
        }


def task_csv_exam_groups():
    """Fichier csv des demi-groupe de TP pour le passage des examens de TP."""

    def csv_exam_groups(target, target_moodle, xls_merge):
        df = pd.read_excel(xls_merge)

        def exam_split(df):
            if 'Tiers-temps' in df.columns:
                dff = df.sort_values('Tiers-temps', ascending=False)
            else:
                dff = df
            n = len(df.index)
            m = math.ceil(n / 2)
            sg1 = dff.iloc[:m, :]['TP'] + 'i'
            sg2 = dff.iloc[m:, :]['TP'] + 'ii'
            dff['TPE'] = pd.concat([sg1, sg2])
            return dff

        if 'TP' not in df.columns:
            return TaskFailed(f"Pas de colonne `TP'; les colonnes sont : {', '.join(df.columns)}")

        dff = df.groupby('TP', group_keys=False).apply(exam_split)
        dff = dff[['Adresse de courriel', 'TPE']]

        with Output(target) as target0:
            dff.to_csv(target0(), index=False)

        with Output(target_moodle) as target:
            dff.to_csv(target(), index=False, header=False)

    for planning, uv, info in selected_uv():
        deps = [generated(task_xls_student_data_merge.target, **info)]
        target = generated('exam_groups.csv', **info)
        target_moodle = generated('exam_groups_moodle.csv', **info)

        yield {
            'name': f'{planning}_{uv}',
            'actions': [(csv_exam_groups, [target, target_moodle, deps[0]])],
            'file_dep': deps,
            'targets': [target_moodle],
            'verbosity': 2
        }


def task_csv_groups():
    """Fichiers csv des groupes de Cours/TD/TP pour Moodle"""

    def csv_groups(target, xls_merge, ctype):
        df = pd.read_excel(xls_merge)
        if ctype not in df.columns:
            return TaskFailed(f"Pas de colonne `{ctype}'; les colonnes sont : {', '.join(df.columns)}")
        dff = df[['Courriel', ctype]]

        with Output(target) as target:
            dff.to_csv(target(), index=False, header=False)

    for planning, uv, info in selected_uv():
        deps = [generated(task_xls_student_data_merge.target, **info)]

        for ctype in ['Cours', 'TD', 'TP']:
            target = generated(f'{ctype}_group_moodle.csv', **info)

            yield {
                'name': f'{planning}_{uv}_{ctype}',
                'actions': [(csv_groups, [target, deps[0], ctype])],
                'file_dep': deps,
                'targets': [target],
                'verbosity': 2
            }


def task_csv_binomes():
    """Fichier csv des groupes + binômes

Variables à fournir:
    planning: (default)
    uv: (default)
    course: Name of column to group by
    project: Identifier of grouping
    other_groups: Other column defining a grouping
"""

    def csv_binomes(target, target_moodle, xls_merge, ctype, project, other_groups):
        df = pd.read_excel(xls_merge)

        def binome_match(row1, row2, other_groups=None, foreign=True):
            "Renvoie vrai si le binôme est bon"

            if foreign:
                e = ['DIPLOME ETAB ETRANGER SECONDAIRE',
                     'DIPLOME ETAB ETRANGER SUPERIEUR',
                     'AUTRE DIPLOME UNIVERSITAIRE DE 1ER CYCLE HORS DUT']

                # 2 étrangers == catastrophe
                if (row1['Dernier diplôme obtenu'] in e and
                    row2['Dernier diplôme obtenu'] in e):
                    return False

                # 2 GB == catastrophe
                if (re.search('^GB', row1['Spécialité 1']) and
                    re.search('^GB', row2['Spécialité 1'])):
                    return False

            # Binomes précédents
            if other_groups is not None:
                for gp in other_groups:
                    if row1[gp] == row2[gp]:
                        return False

            return True

        def trinome_match(row1, row2, row3, other_groups=None):
            return (binome_match(row1, row2, other_groups=other_groups, foreign=False) and
                    binome_match(row1, row3, other_groups=other_groups, foreign=False) and
                    binome_match(row2, row3, other_groups=other_groups, foreign=False))

        class Ooops(Exception):
            pass

        def add_binome(group, other_groups=None, foreign=True):
            gpn = group.name

            while True:
                try:
                    # Création de GROUPS qui associe indice avec groupe
                    index = list(group.index)
                    letters = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')[::-1]
                    l = letters[0]
                    groups = {}
                    maxiter = 1000
                    it = 0
                    while index:
                        it += 1
                        if it > maxiter:
                            raise Ooops
                        if len(index) == 1:
                            # Le binome du dernier groupe
                            stu1, stu2 = [k for k, v in groups.items() if v == l]
                            if trinome_match(group.loc[stu1], group.loc[stu2], group.loc[index[0]], other_groups=other_groups):
                                raise Ooops
                            groups[index[0]] = l
                            index = []
                        else:
                            stu1, stu2 = random.sample(index, 2)
                            if binome_match(group.loc[stu1], group.loc[stu2], other_groups=other_groups, foreign=foreign):
                                l = letters.pop()
                                groups[stu1] = l
                                groups[stu2] = l
                                index.remove(stu1)
                                index.remove(stu2)
                    # do stuff
                except Ooops:
                    continue
                break

            def add_group(g):
                g['binome'] = f'{gpn}_{project}_{g.name}'
                return g

            gb = group.groupby(pd.Series(groups)).apply(add_group)

            return gb

        if ctype not in df.columns:
            return TaskFailed(f"Pas de colonne `{ctype}'; les colonnes sont : {', '.join(df.columns)}")

        gdf = df.groupby(ctype)

        if other_groups is not None:
            if not isinstance(other_groups, list):
                other_groups = [other_groups]

            diff = set(other_groups) - set(df.columns.values)
            if diff:
                s = "s" if len(diff) > 1 else ""
                return TaskFailed(f"Colonne{s} inconnue{s} : `{', '.join(diff)}'; les colonnes sont : {', '.join(df.columns)}")

        df = gdf.apply(add_binome, other_groups=other_groups)
        df = df[['Courriel', ctype, 'binome']]

        # dfa = df[['Adresse de courriel', ctype]].rename(columns={ctype: 'group'})
        dfb = df[['Courriel', 'binome']].rename(columns={'binome': 'group'})
        # df = pd.concat([dfa, dfb])
        df = dfb
        df = df.sort_values('group')

        with Output(target) as target0:
            df.to_csv(target0(), index=False)

        with Output(target_moodle) as target:
            df.to_csv(target(), index=False, header=False)

    uvs = list(selected_uv())
    if len(uvs) == 1:
        planning, uv, info = uvs[0]
        deps = [generated(task_xls_student_data_merge.target, **info)]
        course = get_var('course')
        project = get_var('project')
        other_groups = get_var('other_groups')

        target = generated(f'{course}_{project}_binomes.csv', **info)
        target_moodle = generated(f'{course}_{project}_binomes_moodle.csv', **info)

        return {
            'actions': [(csv_binomes, [target, target_moodle, deps[0], course, project, other_groups])],
            'file_dep': deps,
            'targets': [target_moodle],  # target_moodle only to
                                         # avoid circular dep
            'verbosity': 2
        }
    else:
        return action_msg("Une seule UV doit être sélectionnée")


def skip_days(planning):
    def skip_range(d1, d2):
        return([d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)])

    def skip_week(d1, weeks=1):
        return([d1 + timedelta(days=x) for x in range(7*weeks-1)])

    if planning == 'P2018':
        # Jours fériés
        ferie = [date(2018, 4, 2),
                 date(2018, 5, 1),
                 date(2018, 5, 8),
                 date(2018, 5, 10),
                 date(2018, 5, 21)]

        # Première semaine sans TD/TP
        debut = skip_week(CONFIG['PLANNING'][planning]['PL_BEG'])

        # Semaine des médians
        median = skip_range(date(2018, 5, 2), date(2018, 5, 9))

        # Semaine SU
        semaine_su = skip_week(date(2018, 4, 16), weeks=2)

        # Jours changés
        turn = {
            date(2018, 5, 9): 'Mardi',
            date(2018, 5, 25): 'Lundi'
        }

        # Jours sautés pour Cours/TD/TP
        skip_days_C = ferie + semaine_su + median
        skip_days_D = ferie + semaine_su + debut + median
        skip_days_T = ferie + semaine_su + debut
    elif planning == 'A2018':
        ferie = [date(2018, 10, 18)]  # Comutec

        # Première semaine sans TD/TP
        debut = skip_week(CONFIG['PLANNING'][planning]['PL_BEG'])

        # Semaine des médians
        median = skip_range(date(2018, 11, 6), date(2018, 11, 12))

        noel = skip_range(date(2018, 12, 24), date(2019, 1, 2))

        vacances = skip_range(date(2018, 10, 29), date(2018, 11, 3))

        # Jours changés
        turn = {
            date(2018, 10, 22): 'Jeudi',
            date(2019, 1, 3): 'Lundi'
        }

        # Jours sautés pour Cours/TD/TP
        skip_days_C = vacances + ferie + median + noel
        skip_days_D = vacances + ferie + debut + median + noel
        skip_days_T = vacances + ferie + debut + noel
    elif planning == '2018_T1':
        # Jours fériés
        ferie = [date(2018, 10, 18)]  # Comutec

        vacances = skip_range(date(2018, 10, 29), date(2018, 11, 4))

        # Jours changés
        turn = {
            date(2018, 10, 22): 'Jeudi'
        }

        # Jours sautés pour Cours/TD/TP
        skip_days_C = ferie + vacances
        skip_days_D = ferie + vacances + [date(2018, 9, 10)]
        skip_days_T = ferie + vacances + [date(2018, 9, 10)]

    elif planning == '2018_T2':
        vacances = skip_range(date(2018, 12, 24), date(2019, 1, 2))

        turn = {}

        # Jours sautés pour Cours/TD/TP
        skip_days_C = vacances
        skip_days_D = vacances
        skip_days_T = vacances
    elif planning == 'P2019':
        # Jours fériés
        ferie = [date(2019, 4, 22),
                 date(2019, 5, 1),
                 date(2019, 5, 8),
                 date(2019, 5, 30),
                 date(2019, 6, 10)]

        # Première semaine sans TD/TP
        debut = skip_week(CONFIG['PLANNING'][planning]['PL_BEG'])

        # Semaine des médians
        median = skip_range(date(2019, 4, 23), date(2019, 4, 29))

        vacances = skip_range(date(2019, 4, 15), date(2019, 4, 20))

        # Semaine des finals
        final = skip_range(date(2019, 6, 24), date(2019, 6, 29))

        # Jours changés
        turn = {
            date(2019, 5, 7): 'Mercredi',
            date(2019, 6, 14): 'Lundi'
        }

        # Jours sautés pour Cours/TD/TP
        skip_days_C = ferie + vacances + median + final
        skip_days_D = ferie + vacances + debut + median + final
        skip_days_T = ferie + vacances + debut + final
    else:
        raise Exception('Unsupported planning')

    return skip_days_C, skip_days_D, skip_days_T, turn


def create_plannings(planning_type):
    """Generate list of working days according to planning"""

    def generate_days(beg, end, skip, turn, course):
        daynames = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
        days = []
        delta = end - beg
        semaine = {'Lundi': 0, 'Mardi': 0, 'Mercredi': 0, 'Jeudi': 0, 'Vendredi': 0}

        nweek = 0

        for i in range(delta.days + 1):
            d = beg + timedelta(days=i)

            # Lundi
            if i % 7 == 0:
                nweek += 1

            # Ignore week-end
            if d.weekday() in [5, 6]:
                continue

            # Skip days
            if d in skip:
                continue

            # Get real day
            day = turn[d] if d in turn else daynames[d.weekday()]

            # Get week A or B
            if course == 'T':
                sem = 'A' if semaine[day] % 2 == 0 else 'B'
                numAB = semaine[day] // 2 + 1
                semaine[day] += 1
                num = semaine[day]
            elif course in ['C', 'D']:
                semaine[day] += 1
                numAB = None
                sem = None
                num = semaine[day]
            else:
                raise Exception("course inconnu")

            if d in turn:
                days.append((d, turn[d], sem, num, numAB, nweek))
            else:
                days.append((d, daynames[d.weekday()], sem, num, numAB, nweek))

        return(days)

    beg = CONFIG['PLANNING'][planning_type]['PL_BEG']
    end = CONFIG['PLANNING'][planning_type]['PL_END']
    skip_days_C, skip_days_D, skip_days_T, turn = skip_days(planning_type)
    planning_C = generate_days(beg, end, skip_days_C, turn, 'C')
    planning_D = generate_days(beg, end, skip_days_D, turn, 'D')
    planning_T = generate_days(beg, end, skip_days_T, turn, 'T')

    return({
        'C': planning_C,
        'D': planning_D,
        'T': planning_T
    })


def ical_events(dataframe):
    """Retourne les évènements iCal de tous les cours trouvés dans DATAFRAME"""

    from pytz import timezone
    localtz = timezone('Europe/Paris')

    def timestamp(row):
        d = row['date']
        hm = row['Heure début'].split(':')
        h = int(hm[0])
        m = int(hm[1])
        return(datetime(year=d.year, month=d.month, day=d.day, hour=h, minute=m))

    ts = dataframe.apply(timestamp, axis=1)
    dataframe = dataframe.assign(timestamp=ts.values)
    df = dataframe.sort_values('timestamp')

    cal = Calendar()
    cal['summary'] = CONFIG['DEFAULT_PLANNING']

    for index, row in df.iterrows():
        event = Event()

        uv = row['Code enseig.']
        name = row['Lib. créneau'].replace(' ', '')
        week = row['Semaine']
        room = row['Locaux'].replace(' ', '').replace('BF', 'F')
        num = row['num']
        activity = row['Activité']
        numAB = row['numAB']

        if week is not np.nan:
            summary = f'{uv} {activity}{numAB} {week} {room}'
        else:
            summary = f'{uv} {activity}{num} {room}'

        event.add('summary', summary)

        dt = row['timestamp']
        dt = localtz.localize(dt)
        event.add('dtstart', dt)
        event.add('dtend', dt + timedelta(hours=2))

        cal.add_component(event)

    return cal.to_ical(sorted=True)


def task_ical_inst():
    """Create iCal file for each instructor"""

    def create_ical_inst(insts, plannings, csv):
        tables = [compute_slots(ptype, csv) for ptype in plannings]
        dfm = pd.concat(tables)

        all_insts = dfm['Intervenants'].unique()
        if len(insts) == 1 and insts[0] == 'all':
            insts = all_insts

        if set(insts).issubset(set(all_insts)):
            if len(insts) == 1:
                inst = insts[0]
                dfm_inst = dfm.loc[dfm['Intervenants'].astype(str) == inst, :]
                output = generated(f'{inst.replace(" ", "_")}.ics')
                events = ical_events(dfm_inst)
                with Output(output) as output:
                    with open(output(), 'wb') as fd:
                        fd.write(events)
            else:
                temp_dir = tempfile.mkdtemp()
                for inst in insts:
                    dfm_inst = dfm.loc[dfm['Intervenants'].astype(str) == inst, :]
                    events = ical_events(dfm_inst)

                    output = f'{inst.replace(" ", "_")}.ics'
                    with open(os.path.join(temp_dir, output), 'wb') as fd:
                        fd.write(events)

                output = generated(f'ics.zip')
                with Output(output) as output0:
                    with zipfile.ZipFile(output0(), 'w') as z:
                        for filepath in glob.glob(os.path.join(temp_dir, '*.ics')):
                            z.write(filepath, os.path.basename(filepath))

        else:
            unknown = set(insts).difference(all_insts)
            return TaskFailed(f"Intervenant(s) inconnu(s): {', '.join(unknown)}")

    deps = [generated(task_add_instructors.target)]

    plannings = get_var('planning', '')
    if plannings:
        plannings = plannings.split()
    else:
        plannings = CONFIG['DEFAULT_PLANNINGS']

    insts = get_var('insts', '')
    if insts:
        insts = insts.split()
    else:
        insts = [CONFIG['DEFAULT_INSTRUCTOR']]

    return {
        'file_dep': deps,
        'actions': [(create_ical_inst, [insts, plannings, deps[0]])],
        'uptodate': [False],
        'verbosity': 2
    }


@add_templates(target='UTC_UV_list_créneau.csv')
def task_csv_all_courses():
    "Fichier csv de tous les créneaux du semestre"

    def csv_all_courses(plannings, csv, target):
        df = pd.read_csv(csv)

        tables = []
        for planning_type in plannings:
            uv = (CONFIG['PLANNING'][planning_type].get('UV') or
                  CONFIG['PLANNING'][planning_type].get('UE'))
            df_planning = df.loc[df['Code enseig.'].isin(uv)]
            planning = create_plannings(planning_type)

            planning_C = planning['C']
            pl_C = pd.DataFrame(planning_C)
            pl_C.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

            df_C = df_planning.loc[df_planning['Lib. créneau'].str.startswith('C'), :]
            df_Cm = pd.merge(df_C, pl_C, how='left', left_on='Jour', right_on='dayname')

            planning_D = planning['D']
            pl_D = pd.DataFrame(planning_D)
            pl_D.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

            df_D = df_planning.loc[df_planning['Lib. créneau'].str.startswith('D'), :]
            df_Dm = pd.merge(df_D, pl_D, how='left', left_on='Jour', right_on='dayname')

            planning_T = planning['T']
            pl_T = pd.DataFrame(planning_T)
            pl_T.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

            df_T = df_planning.loc[df_planning['Lib. créneau'].str.startswith('T'), :]
            if df_T['Semaine'].hasnans:
                df_Tm = pd.merge(df_T, pl_T, how='left', left_on='Jour', right_on='dayname')
            else:
                df_Tm = pd.merge(df_T, pl_T, how='left', left_on=['Jour', 'Semaine'], right_on=['dayname', 'semaine'])

            dfm = pd.concat([df_Cm, df_Dm, df_Tm], ignore_index=True)
            tables.append(dfm)

        dfm = pd.concat(tables)
        with Output(target) as target:
            dfm.to_csv(target(), index=False)

    dep = generated(task_add_instructors.target)
    target = generated(task_csv_all_courses.target)

    plannings = get_var('plannings') or CONFIG['DEFAULT_PLANNINGS']
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
        slots = compute_slots(planning, csv_inst_list)
        slots = slots.loc[slots['Code enseig.'] == uv, :]
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
        for (mon, nmon) in mondays(CONFIG['PLANNING'][planning]['PL_BEG'],
                                   CONFIG['PLANNING'][planning]['PL_END']):
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


def compute_slots(planning_type, csv_inst_list):
    """Renvoie la liste des créneaux sur tout le semestre"""

    df = pd.read_csv(csv_inst_list)
    df_planning = df.loc[(~pd.isnull(df['Intervenants'])) &
                         (df['Planning'] == planning_type), :]
    planning = create_plannings(planning_type)

    planning_C = planning['C']
    pl_C = pd.DataFrame(planning_C)
    pl_C.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

    df_C = df_planning.loc[df_planning['Lib. créneau'].str.startswith('C'), :]
    df_Cm = pd.merge(df_C, pl_C, how='left', left_on='Jour', right_on='dayname')

    planning_D = planning['D']
    pl_D = pd.DataFrame(planning_D)
    pl_D.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

    df_D = df_planning.loc[df_planning['Lib. créneau'].str.startswith('D'), :]
    df_Dm = pd.merge(df_D, pl_D, how='left', left_on='Jour', right_on='dayname')

    planning_T = planning['T']
    pl_T = pd.DataFrame(planning_T)
    pl_T.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

    df_T = df_planning.loc[df_planning['Lib. créneau'].str.startswith('T'), :]
    if df_T['Semaine'].hasnans:
        df_Tm = pd.merge(df_T, pl_T, how='left', left_on='Jour', right_on='dayname')
    else:
        df_Tm = pd.merge(df_T, pl_T, how='left', left_on=['Jour', 'Semaine'], right_on=['dayname', 'semaine'])

    dfm = pd.concat([df_Cm, df_Dm, df_Tm], ignore_index=True)
    return dfm


def task_json_restriction():
    """Ficher json des restrictions d'accès des TP"""

    sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts/'))
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


def task_pdf_trombinoscope():
    """Fichier PDF des trombinoscopes par groupes et/ou sous-groupes"""

    def pdf_trombinoscope(xls_merge, target, groupby, subgroupby, width):
        async def download_image(session, login):
            url = URL + login
            async with session.get(url) as response:
                content = await response.content.read()
                if len(content) < 100:
                    copyfile(os.path.join(os.path.dirname(__file__), 'documents/inconnu.jpg'),
                             common_doc(f'images/{login}.jpg'))
                else:
                    with open(common_doc(f'images/{login}.jpg'), 'wb') as handler:
                        handler.write(content)

        def md5(fname):
            hash_md5 = hashlib.md5()
            with open(fname, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()

        async def download_session(loop):
            os.makedirs(generated('images'), exist_ok=True)
            async with aiohttp.ClientSession(loop=loop) as session:
                md5_inconnu = md5(os.path.join(os.path.dirname(__file__), 'documents/inconnu.jpg'))
                for login in df.Login:
                    md5_curr = md5(generated(f'images/{login}.jpg'))
                    if not os.path.exists(generated(f'images/{login}.jpg')) or md5_curr == md5_inconnu:
                        await download_image(session, login)

        # Getting images
        df = pd.read_excel(xls_merge)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(download_session(loop))

        jinja_dir = os.path.join(os.path.dirname(__file__), 'templates')
        latex_jinja_env = jinja2.Environment(
            block_start_string='((*',
            block_end_string='*))',
            variable_start_string='(((',
            variable_end_string=')))',
            comment_start_string='((=',
            comment_end_string='=))',
            loader=jinja2.FileSystemLoader(jinja_dir))
        latex_jinja_env.filters['escape_tex'] = escape_tex

        temp_dir = tempfile.mkdtemp()
        tmpl = latex_jinja_env.get_template('trombinoscope_template_2.tex.jinja2')

        # On vérifie que GROUPBY et SUBGROUPBY sont licites
        if groupby != 'all' and groupby not in df.columns:
            return TaskFailed(f"No column `{groupby}' to group by")
        if groupby == 'all':
            groupby = None
        if subgroupby is not None and subgroupby not in df.columns:
            return TaskFailed(f"No column `{subgroupby}' to subgroup by")

        # Diviser par groupe de TP/TP
        for title, group in df.groupby(groupby or (lambda x: "all")):

            # Diviser par binomes, sous-groupes
            dff = group.groupby(subgroupby or (lambda x: 0))

            # Nom de fichier
            if len(dff) == 1:
                fn = title + ".pdf"
            else:
                fn = title + '_' + subgroupby + ".pdf"
            data = []
            # Intérer sur ces sous-groupes des groupes de TP/TD
            for name, df_group in dff:
                group = {}
                if len(dff) != 1:
                    group['title'] = name

                rows = []
                dfs = df_group.sort_values(['Nom', 'Prénom'])
                # Grouper par WIDTH sur une ligne si plus de WIDTH
                for _, df_row in dfs.groupby(np.arange(len(df_group.index)) // width):
                    cells = []
                    for _, row in df_row.iterrows():
                        path = os.path.abspath(common_doc(f'images/{row["Login"]}.jpg'))
                        cell = {'name': row['Prénom'],
                                'lastname': row['Nom'],
                                'photograph': path}
                        cells.append(cell)
                    rows.append(cells)

                group['rows'] = rows
                data.append(group)

            tex = tmpl.render(title=title, data=data, width='c'*width)
            # with open(target0+'.tex', 'w') as fd:
            #     fd.write(tex)

            pdf = latex.build_pdf(tex)
            pdf.save_to(os.path.join(temp_dir, fn))

        # with Output(fn) as target0:
        #     pdf.save_to(target0())
        with Output(target) as target0:
            with zipfile.ZipFile(target0(), 'w') as z:
                for filepath in glob.glob(os.path.join(temp_dir, '*.pdf')):
                    z.write(filepath, os.path.basename(filepath))


    group = get_var('group')
    subgroup = get_var('subgroup')

    for planning, uv, info in selected_uv():
        dep = generated(task_xls_student_data_merge.target, **info)
        if group:
            if subgroup:
                target = generated(f'trombi_{group}_{subgroup}.zip', **info)
            else:
                target = generated(f'trombi_{group}.zip', **info)

            yield {
                'name': f'{planning}_{uv}',
                'file_dep': [dep],
                'targets': [target],
                'actions': [(pdf_trombinoscope, [dep, target, group, subgroup, 5])],
                'uptodate': [False],
                'verbosity': 2
            }
        else:
            yield action_msg("Argument manquant: `group=<colname>'", name=f'{planning}_{uv}')



def task_pdf_attendance_list():
    """Fichier pdf de fiches de présence"""

    def pdf_attendance_list(xls_merge, group, target):
        df = pd.read_excel(xls_merge)

        jinja_dir = os.path.join(os.path.dirname(__file__), 'templates')
        latex_jinja_env = jinja2.Environment(
            block_start_string='((*',
            block_end_string='*))',
            variable_start_string='(((',
            variable_end_string=')))',
            comment_start_string='((=',
            comment_end_string='=))',
            loader=jinja2.FileSystemLoader(jinja_dir))

        template = latex_jinja_env.get_template('attendance_list.tex.jinja2')

        temp_dir = tempfile.mkdtemp()
        for gn, group in df.groupby(group):
            group = group.sort_values(['Nom', 'Prénom'])

            students = [{'name': f'{row["Nom"]} {row["Prénom"]}'}
                        for _, row in group.iterrows()]
            tex = template.render(students=students, group=f'Groupe: {gn}')

            # with open(target0+'.tex', 'w') as fd:
            #     fd.write(tex)

            pdf = latex.build_pdf(tex)
            pdf.save_to(os.path.join(temp_dir, gn + ".pdf"))

        with Output(target) as target0:
            with zipfile.ZipFile(target0(), 'w') as z:
                for filepath in glob.glob(os.path.join(temp_dir, '*.pdf')):
                    z.write(filepath, os.path.basename(filepath))

    uvs = list(selected_uv())
    if len(uvs) == 1:
        planning, uv, info = uvs[0]
        group = get_var('group')
        if group:
            xls_merge = generated(task_xls_student_data_merge.target, **info)
            target = generated(f'attendance_{group}.zip', **info)
            return {
                'file_dep': [xls_merge],
                'targets': [target],
                'actions': [(pdf_attendance_list, [xls_merge, group, target])],
                'verbosity': 2
            }
        else:
            return action_msg('Il faut fournir un nom de colonne de `*_student_data_merge.xlsx` pour grouper.')
    else:
        return action_msg("Une seule UV doit être sélectionnée")


def task_xls_assignment_grade():
    """Création d'un fichier Excel pour remplissage des notes par les intervenants"""

    def xls_assignment_grade(inst_uv, xls_merge, target):
        inst_uv = pd.read_excel(inst_uv)
        TD = inst_uv['Lib. créneau'].str.contains('^D')
        inst_uv_TD = inst_uv.loc[TD]
        insts = inst_uv_TD['Intervenants'].unique()

        df = pd.read_excel(xls_merge)
        df = df[['Nom', 'Prénom', 'Courriel']].sort_values(['Nom', 'Prénom'])
        df = df.assign(Note=np.nan)

        with Output(target) as target:
            writer = pd.ExcelWriter(target())
            for inst in insts:
                df.to_excel(writer, sheet_name=inst, index=False)
            writer.save()

    uvs = list(selected_uv())
    if len(uvs) == 1:
        exam = get_var('exam')
        if exam:
            planning, uv, info = uvs[0]
            xls_merge = generated(task_xls_student_data_merge.target, **info)
            inst_uv = documents(task_xls_affectation.target, **info, **info)
            target = generated(f'{exam}.xlsx', **info)
            return {
                'file_dep': [xls_merge, inst_uv],
                'targets': [target],
                'actions': [(xls_assignment_grade, [inst_uv, xls_merge, target])],
                'verbosity': 2
            }
        else:
            return action_msg("Il faut spécifier le nom de l'examen")
    else:
        return action_msg("Une seule UV doit être sélectionnée")


def task_attendance_sheet():
    """Fichier pdf de feuilles de présence"""

    def generate_attendance_sheets(groupby, target, **kwargs):
        groupby = {}
        while True:
            room = input('Salle: ')
            num = input('Nombre: ')
            if not room:
                if not num:
                    if groupby:
                        print('Liste des salles: \n%s' % groupby)
                        break
                    else:
                        raise
            elif re.fullmatch('[0-9]+', num):
                groupby[room] = int(num)

        if isinstance(groupby, tuple):
            sort_cols = kwargs.get('sort_cols')

        elif isinstance(groupby, dict):
            jinja_dir = os.path.join(os.path.dirname(__file__), 'templates')
            latex_jinja_env = jinja2.Environment(
                block_start_string='((*',
                block_end_string='*))',
                variable_start_string='(((',
                variable_end_string=')))',
                comment_start_string='((=',
                comment_end_string='=))',
                loader=jinja2.FileSystemLoader(jinja_dir))

            template = latex_jinja_env.get_template('attendance_list_noname.tex.jinja2')

            for room, number in groupby.items():
                tex = template.render(number=number, group=f'Salle {room}')

                target0 = target % room
                # with open(target0+'.tex', 'w') as fd:
                #     fd.write(tex)

                pdf = latex.build_pdf(tex)
                pdf.save_to(target0)

    groupby = {
        'FA300': 90,
        'FA321': 70,
        'FA310': 50
    }

    uvs = list(selected_uv())
    if len(uvs) != 1:
        return action_msg("Une seule UV doit être sélectionnée")
    exam = get_var('exam')
    if not exam:
        return action_msg("Il faut spécifier le nom de l'examen")

    pl, uv, info = uvs[0]
    target = generated(f'{exam}_présence_%s.pdf', **info)
    return {
        'targets': [target],
        'actions': [(generate_attendance_sheets, [groupby, target])],
        'verbosity': 2
    }


def task_csv_for_upload():
    """Fichier csv de notes prêtes à être chargées sur l'ENT.

Prend les informations dans le fichier
'generated/{planning}_{uv}_student_data_merge.xlsx' grâce aux
variables fournies en arguments: PLANNING, UV, GRADE_COLNAME,
COMMENT_COLNAME.
    """

    def csv_for_upload(csv_fname, xls_merge, grade_colname, comment_colname):
        if grade_colname is None:
            raise Exception('Missing grade_colname')

        df = pd.read_excel(xls_merge)
        cols = {
            'Nom': df.Nom,
            'Prénom': df['Prénom'],
            'Login': df.Login,
            'Note': df[grade_colname],
        }
        col_names = ['Nom', 'Prénom', 'Login', 'Note']
        if comment_colname is not None:
            col_names.append('Commentaire')
            cols['Commentaire'] = np.where(df[comment_colname].isnull(),
                                           np.nan,
                                           'Corrigé par ' + df[comment_colname])

        df0 = pd.DataFrame(cols, columns=col_names)
        df0 = df0[col_names]
        df0 = df0.sort_values(['Nom', 'Prénom'])

        with Output(csv_fname) as csv_fname:
            df0.to_csv(csv_fname(), index=False, sep=';')

    uvs = list(selected_uv())
    if len(uvs) == 1:
        grade_colname = get_var('grade_colname')
        comment_colname = get_var('comment_colname')
        if grade_colname:
            planning, uv, info = uvs[0]
            csv_fname = generated('{grade_colname}_ENT.csv', **info)
            xls_merge = generated(task_xls_student_data_merge.target, **info)
            deps = [generated(task_xls_student_data_merge.target, **info)]
            return {
                'actions': [(csv_for_upload, [csv_fname, xls_merge, grade_colname, comment_colname])],
                'targets': [csv_fname],
                'file_dep': deps
            }
        else:
            return action_msg("Il faut spécifier le nom de la colonne")
    else:
        return action_msg("Une seule UV doit être sélectionnée")


def task_xls_merge_final_grade():
    """Fichier Excel des notes finales attribuées

Transforme un classeur Excel avec une feuille par correcteur en une
seule feuille où les notes sont concaténées pour fusion/révision
manuelle."""

    def xls_merge_final_grade(xls_sheets, xls_grades):
        xls = pd.ExcelFile(xls_sheets)
        dfall = xls.parse(xls.sheet_names[0])
        dfall = dfall[['Nom', 'Prénom', 'Courriel']]

        dfs = []
        for sheet in xls.sheet_names:
            df = xls.parse(sheet)
            df = df.loc[~df.Note.isnull()]
            df['Correcteur médian'] = sheet
            dfs.append(df)
        # Concaténation de tous les devoirs qui ont une note
        df = pd.concat(dfs, axis=0)

        # On rattrape les absents
        df = pd.merge(dfall, df, how='left', on=['Nom', 'Prénom', 'Courriel'])
        df = df.sort_values(['Nom', 'Prénom'])

        csv_grades = os.path.splitext(xls_grades)[0] + '.csv'
        with Output(csv_grades, protected=True) as csv_grades:
            df.to_csv(csv_grades(), index=False)

        with Output(xls_grades, protected=True) as xls_grades:
            df.to_excel(xls_grades(), index=False)

        # def max_grade(group):
        #     return group.loc[df['Note'].idxmax()]

        # dff = df.groupby(['Nom', 'Prénom'], group_keys=False).apply(max_grade)
        # dff.to_excel(xls_grades, index=False)

    uvs = list(selected_uv())
    if len(uvs) == 1:
        pl, uv, info = uvs[0]
        exam = get_var('exam')
        if exam:
            xls_sheets = documents('{exam}.xlsx', **info)
            xls_grades = documents('{exam}_notes.xlsx', **info)

            return {
                'actions': [(xls_merge_final_grade, [xls_sheets, xls_grades])],
                'targets': [xls_grades],
                'file_dep': [xls_sheets],
                'verbosity': 2
            }
        else:
            return action_msg("Il faut spécifier le nom de l'examen")
    else:
        return action_msg("Une seule UV doit être sélectionnée")


def task_xls_grades_sheet():
    """Génère un fichier Excel pour faciliter la correction des examens/projets/jury"""

    sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts/'))
    from xls_gradebook import run, arg

    cmd_args = get_var("args", "").split() + ['-o', 'documents/', '-d', 'generated/']
    cmd_args = sys.argv[2:] + ['-o', 'documents/', '-d', 'generated/']

    data_file = arg(sys.argv[2:] + ['-o', 'documents/', '-d', 'generated/'])

    return {
        'actions': [(run, [cmd_args])],
        'file_dep': [data_file] if data_file else [],
        'params': ([{'name': arg,
                     'long': arg,
                     'default': 'dummy'} for arg in ['type', 'name', 'uv', 'planning', 'data', 'output-file', 'struct', 'group', 'config']] +
                   [{'name': arg,
                     'short': arg,
                     'default': 'dummy'} for arg in ['d', 'o', 's', 'g', 'c']] +
                   [{'name': arg,
                     'short': arg,
                     'type': bool,
                     'default': 'dummy'} for arg in ['h']]),
        'verbosity': 2,
        'uptodate': [False]
    }

def task_yaml_QCM():
    """Génère un fichier yaml prérempli pour noter un QCM"""

    def yaml_QCM(yaml_fname, xls_merge):
        df = pd.read_excel(xls_merge)
        dff = df[['Nom', 'Prénom', 'Courriel']]
        d = dff.to_dict(orient='index')
        rec = [{'Nom': record['Nom'] + ' ' + record['Prénom'],
                'Courriel': record['Courriel'],
                'Resultat': ''} for record in d.values()]

        rec = {'Students': rec, 'Answers': ''}

        with Output(yaml_fname, protected=True) as yaml_fname:
            with open(yaml_fname(), 'w') as fd:
                yaml.dump(rec, fd, default_flow_style=False)

    uvs = list(selected_uv())
    if len(uvs) == 1:
        planning, uv, info = uvs[0]
        xls_merge = generated(task_xls_student_data_merge.target, **info)
        yaml_fname = generated('QCM.yaml', **info)
        return {
            'actions': [(yaml_QCM, [yaml_fname, xls_merge])],
            'targets': [yaml_fname],
            'file_dep': [xls_merge],
            'verbosity': 2
        }
    else:
        return action_msg("Une seule UV doit être sélectionnée")
