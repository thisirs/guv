import os
import re
import glob
import tempfile
import zipfile
import jinja2
import markdown

import pandas as pd
from pandas.api.types import CategoricalDtype

from doit.exceptions import TaskFailed

from .config import settings
from .dodo_utc import task_utc_uv_list_to_csv
from .utils import (
    Output,
    add_templates,
    documents,
    generated,
    selected_uv,
    compute_slots,
    ical_events,
    create_cal_from_dataframe,
    parse_args,
    argument,
    actionfailed_on_exception
)
from .scripts.excel_hours import create_excel_file


@add_templates(target='intervenants.xlsx')
def task_xls_instructors():
    doc = documents(task_xls_instructors.target)

    def xls_instructors(doc):
        if not os.path.exists(doc):
            return TaskFailed(f"Pas de fichier `{doc}'")

    return {
        'actions': [(xls_instructors, [doc])],
        'targets': [doc]
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
    uv_list = documents(task_utc_uv_list_to_csv.target)
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

    insts_details = documents(task_xls_instructors.target)

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
            return crs, no, sem

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

    insts = documents(task_xls_instructors.target)
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

    uvlist_csv = documents(task_utc_uv_list_to_csv.target)
    for planning, uv, info in selected_uv():
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

    for planning, uv, info in selected_uv():
        uv_list = documents(task_xls_affectation.target, **info)
        target = generated(task_cal_uv.target, **info)

        yield {
            'name': f'{planning}_{uv}',
            'file_dep': [uv_list, template],
            'targets': [target],
            'actions': [(create_cal_from_list, [uv, uv_list, target])]
        }


@actionfailed_on_exception
def task_cal_inst():
    """Calendrier PDF d'une semaine de toutes les UV/UE d'un intervenant."""

    def create_cal_from_list(inst, plannings, uv_list_filename, target):
        df = pd.read_csv(uv_list_filename)
        if 'Intervenants' not in df.columns:
            raise Exception('Pas d\'enregistrement des intervenants')

        df_inst = df.loc[(df['Intervenants'].astype(str) == inst) &
                         (df['Planning'].isin(plannings)), :]
        text = r'{uv} \\ {name} \\ {room}'
        create_cal_from_dataframe(df_inst, text, target)

    args = parse_args(
        task_cal_inst,
        argument('-p', '--plannings', nargs='*', default=settings.SELECTED_PLANNINGS),
        argument('-i', '--insts', nargs='*', default=[settings.DEFAULT_INSTRUCTOR])
    )

    uv_list = generated(task_add_instructors.target)
    jinja_dir = os.path.join(os.path.dirname(__file__), 'templates')
    template = os.path.join(jinja_dir, 'calendar_template.tex.jinja2')

    for inst in args.insts:
        target = generated(f'{inst.replace(" ", "_")}_{"_".join(args.plannings)}_calendrier.pdf')

        yield {
            'name': '_'.join(args.plannings) + '_' + inst,
            'targets': [target],
            'file_dep': [uv_list, template],
            'actions': [(create_cal_from_list, [inst, args.plannings, uv_list, target])],
        }


@actionfailed_on_exception
def task_ical_inst():
    """Create iCal file for each instructor"""

    def create_ical_inst(insts, plannings, csv):
        tables = [compute_slots(csv, ptype, empty_instructor=False) for ptype in plannings]
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

    args = parse_args(
        task_ical_inst,
        argument('-p', '--plannings', nargs='+', default=settings.SELECTED_PLANNINGS),
        argument('-i', '--insts', nargs='+', default=[settings.DEFAULT_INSTRUCTOR])
    )

    deps = [generated(task_add_instructors.target)]

    return {
        'actions': [(create_ical_inst, [args.insts, args.plannings, deps[0]])],
        'file_dep': deps,
        'uptodate': [False],
        'verbosity': 2
    }
