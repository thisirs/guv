import re
import jinja2
import latex
import pandas as pd
from icalendar import Event, Calendar
from datetime import datetime, date, timedelta
from tabula import read_pdf


def task_xls_UTP():
    """Crée un document Excel pour calcul des heures et remplacements."""

    import sys
    sys.path.append('scripts/')
    from excel_hours import create_excel_file

    def create_excel_file0(inst_fn, target):
        with open(inst_fn) as fd:
            instructors = [line.rstrip() for line in fd]
            create_excel_file(target, instructors)

    inst_fn = 'documents/instructor_list.raw'
    target = 'generated/SY02_remplacement.xlsx'

    return {
        'file_dep': [inst_fn],
        'targets': [target],
        'actions': [(create_excel_file0, [inst_fn, target])]
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

        df.to_csv(target, index=False)

    uv_list_filename = 'documents/UTC_UV_list.pdf'
    target = 'generated/UTC_UV_list.csv'

    return {
        'file_dep': [uv_list_filename],
        'targets': [target],
        'actions': [(utc_uv_list_to_csv, [uv_list_filename, target])]
    }


def task_xls_affectation():
    """Crée un fichier Excel avec les libellés des séances et les chargés
    de Cours/TD/TP à remplir avant d'être fusionnée."""

    uvlist_csv = 'generated/UTC_UV_list.csv'
    target = 'generated/SY02_chargés.xls'
    uv = 'SY02'

    def extract_uv_instructor(uv_list_filename, uv, target):
        df = pd.read_csv(uv_list_filename)
        df_uv = df.loc[df['Code enseig.'] == uv, :]
        df_uv_real = df_uv.loc[df['Type créneau'] == 'Groupe actif', :]

        selected_columns = ['Jour', 'Heure début', 'Heure fin', 'Locaux', 'Semaine', 'Lib. créneau']
        df_uv_real = df_uv_real[selected_columns]
        df_uv_real["Chargés"] = ""

        df_uv_real.to_excel(target, sheet_name='Chargés', index=False)

    return {
        'file_dep': [uvlist_csv],
        'targets': [target],
        'actions': [(extract_uv_instructor, [uvlist_csv, uv, target])]
    }


def task_cal_inst():
    """Calendrier PDF de tous les intervenants"""

    uv = 'SY02'
    uv_list = 'generated/UTC_UV_list_instructors.csv'

    def create_cal_from_list(uv, uv_list_filename):
        df = pd.read_csv(uv_list_filename)
        if 'Chargés' not in df.columns:
            raise StandardError('Pas d\'enregistrement des intervenants')
        df_uv = df.loc[df['Code enseig.'] == uv, :]
        df_uv_real = df_uv.loc[df['Type créneau'] == 'Groupe actif', :]

        text = r'{name} \\ {room} \\ {author}'
        for instructor, group in df_uv_real.groupby(['Chargés']):
            target = f'generated/{uv}_{instructor}_calendrier.pdf'
            create_cal_from_dataframe(group, text, target)

    return {
        'file_dep': [uv_list],
        # 'targets': [target],
        'actions': [(create_cal_from_list, [uv, uv_list])]
    }


def task_add_instructors():
    """Ajoute les intervenants dans la liste csv des créneaux"""

    deps = ['generated/UTC_UV_list.csv', 'generated/SY02_chargés_rempli.xls']
    target = 'generated/UTC_UV_list_instructors.csv'

    def add_instructors(csv, inst):
        df_csv = pd.read_csv(csv)
        df_inst = pd.read_excel(inst)

        df_merge = pd.merge(df_csv, df_inst, how='left', on=['Jour', 'Heure début', 'Heure fin', 'Semaine', 'Lib. créneau', 'Locaux'])

        df_merge.to_csv(target, index=False)

    return {
        'file_dep': deps,
        'targets': [target],
        'actions': [(add_instructors, deps)]
    }


def create_cal_from_dataframe(df, text, target):
    """Crée un calendrier avec text dans les cases"""

    # 08:15 should be 8_00
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

    # Returns blocks like \node[2hours, full, {course}] at ({day}-{bh}) {{{text}}};
    def build_block(row, text, half=False):
        uv = row['Code enseig.']

        name = row['Lib. créneau'].replace(' ', '')
        if re.match('^T', name):
            ctype = 'TP'
            if row['Semaine'] == 'semaine A':
                name = name + 'A'
            elif row['Semaine'] == 'semaine B':
                name = name + 'B'
        elif re.match('^D', name):
            ctype = 'TD'
        elif re.match('^C', name):
            ctype = 'Cours'

        if 'Chargés' in row.keys():
            if pd.isnull(row['Chargés']):
                author = 'N/A'
            else:
                author = row['Chargés']
        else:
            author = 'N/A'

        room = row['Locaux']
        room = room.replace(' ', '').replace('BF', 'F')

        text = text.format(room=room, name=name, author=author)
        bh = convert_time(row['Heure début'])
        day = convert_day(row['Jour'])

        if not half:
            half = 'full'
        return(rf'\node[2hours, {half}, {ctype}] at ({day}-{bh}) {{{text}}};')

    blocks = []
    for hour, group in df.groupby(['Jour', 'Heure début', 'Heure fin']):
        if len(group) > 2:
            raise StandardError("Trop de créneaux en même temps")
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
    pdf = latex.build_pdf(tex)
    pdf.save_to(target)


def task_cal_uv():
    """Calendrier PDF global de l'UV"""

    uv = 'SY02'
    uv_list = 'generated/UTC_UV_list_instructors.csv'
    target = 'generated/' + uv + '_calendrier.pdf'

    def create_cal_from_list(uv, uv_list_filename, target):
        df = pd.read_csv(uv_list_filename)
        df_uv = df.loc[df['Code enseig.'] == uv, :]
        df_uv_real = df_uv.loc[df['Type créneau'] == 'Groupe actif', :]
        text = r'{name} \\ {room} \\ {author}'
        return(create_cal_from_dataframe(df_uv_real, text, target))

    return {
        'file_dep': [uv_list],
        'targets': [target],
        'actions': [(create_cal_from_list, [uv, uv_list, target])]
    }


def task_utc_listing_to_csv():
    """Construit un fichier CSV à partir des données brutes de la promo
    fournies par l'UTC."""

    utc_listing = 'documents/SY02_P2018_INSCRITS.raw'

    return {
        'file_dep': [utc_listing],
        'targets': ['generated/SY02_P2018_INSCRITS.csv'],
        'actions': [['scripts/']]
    }


def task_merge_utc_moodle_csv():
    """Construit un fichier CSV unique avec les informations de Moodle et
    de l'UTC."""

    moodle_listing = 'documents/SY02_P2018_MOODLE.csv'
    utc_listing_csv = 'generated/SY02_P2018_INSCRITS.csv'
    tiers_temps = 'documents/SY02_P2018_TIERS_TEMPS.lst'

    return {
        'file_dep': [moodle_listing, utc_listing_csv, tiers_temps],
        'targets': ['generated/SY02_P2018_UTC_MOODLE_MERGE.csv'],
        'actions': [['scripts/']]
    }


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
    median = skip_week(date(2018, 4, 30))

    semaine_su = skip_week(date(2018, 4, 16), weeks=2)

    turn = {
        date(2018, 5, 9): 'Mercredi',
        date(2018, 5, 25): 'Lundi'
    }

    skip_days_C = ferie + semaine_su
    skip_days_D = ferie + semaine_su + debut + median
    skip_days_T = ferie + semaine_su + debut

    beg = date(2018, 2, 19)
    end = date(2018, 6, 22)

    def generate_days(beg, end, skip, turn, course):
        daynames = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
        days = []
        delta = end - beg
        semaine = {'Lundi': 0, 'Mardi': 0, 'Mercredi': 0, 'Jeudi': 0, 'Vendredi': 0}

        for i in range(delta.days + 1):
            d = beg + timedelta(days=i)
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
                semaine[day] += 1
            else:
                sem = None

            if d in turn:
                days.append((d, turn[d], sem))
            else:
                days.append((d, daynames[d.weekday()], sem))

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
    deps = ['generated/UTC_UV_list_instructors.csv']

    def create_ical_inst(csv):
        df = pd.read_csv(csv)
        df = df.loc[~pd.isnull(df['Chargés']), :]

        planning = create_plannings()

        planning_C = planning['C']
        pl_C = pd.DataFrame(planning_C)
        pl_C.columns = ['date', 'dayname', 'semaine']

        df_C = df.loc[df['Lib. créneau'].str.startswith('C'), :]
        df_Cm = pd.merge(df_C, pl_C, how='left', left_on='Jour', right_on='dayname')

        planning_D = planning['D']
        pl_D = pd.DataFrame(planning_D)
        pl_D.columns = ['date', 'dayname', 'semaine']

        df_D = df.loc[df['Lib. créneau'].str.startswith('D'), :]
        df_Dm = pd.merge(df_D, pl_D, how='left', left_on='Jour', right_on='dayname')

        planning_T = planning['T']
        pl_T = pd.DataFrame(planning_T)
        pl_T.columns = ['date', 'dayname', 'semaine']

        df_T = df.loc[df['Lib. créneau'].str.startswith('T'), :]
        df_Tm = pd.merge(df_T, pl_T, how='left', left_on='Jour', right_on='dayname')

        dfm = pd.concat([df_Cm, df_Dm, df_Tm], ignore_index=True)

        for inst, group in dfm.groupby('Chargés'):
            output = f'generated/{inst}.ics'
            write_ical_file(group, output)

    return {
        'file_dep': ['generated/UTC_UV_list_instructors.csv'],
        'actions': [(create_ical_inst, deps)]
    }


def write_ical_file(dataframe, output):
    cal = Calendar()
    cal['summary'] = 'SY02'
    for index, row in dataframe.iterrows():
        event = Event()
        summary = '{0[Code enseig.]} {0[Activité]} {0[Locaux]}'.format(row)
        event.add('summary', summary)

        d = row['date']
        hm = row['Heure début'].split(':')
        h = int(hm[0])
        m = int(hm[1])
        dt = datetime(year=d.year, month=d.month, day=d.day, hour=h, minute=m)
        event.add('dtstart', dt)

        event.add('dtend', dt + timedelta(hours=2))

        cal.add_component(event)

    with open(output, 'wb') as fd:
        fd.write(cal.to_ical(sorted=True))
