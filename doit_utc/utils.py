import os
import sys
import re
import time
import argparse
import hashlib
import unidecode
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from icalendar import Event, Calendar
import latex
import jinja2
import textwrap
from functools import wraps
from types import SimpleNamespace, GeneratorType

from doit.exceptions import TaskFailed

from .config import settings


def actionfailed_on_exception(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            ret = func(*args, **kwargs)
            if isinstance(ret, GeneratorType):
                ret = (t for t in list(ret))
            return ret
        except Exception as e:
            tf = TaskFailed(e.args)
            action = {
                'actions': [lambda: tf],
            }
            return action
    return wrapper


def taskfailed_on_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return TaskFailed(e.args)
    return wrapper


def check_columns(dataframe, columns, **kwargs):
    if isinstance(columns, str):
        columns = [columns]
    missing_cols = [c for c in columns if c not in dataframe.columns]

    if missing_cols:
        s = "s" if len(missing_cols) > 1 else ""
        missing_cols = ", ".join(f"`{e}'" for e in missing_cols)
        avail_cols = ", ".join(f"`{e}'" for e in dataframe.columns)
        if 'file' in kwargs:
            msg = f"Colonne{s} manquante{s}: {missing_cols} dans le dataframe issu du fichier {kwargs['file']}. Colonnes disponibles: {avail_cols}"
        else:
            msg = f"Colonne{s} manquante{s}: {missing_cols}. Colonnes disponibles: {avail_cols}"
        raise Exception(msg)


def parse_args(task, *args, **kwargs):
    name = task.__name__.split("_", maxsplit=1)[1]

    parser = argparse.ArgumentParser(
        description=task.__doc__,
        prog=f"doit-utc {name}"
    )

    argv = sys.argv if 'argv' not in kwargs else kwargs['argv']

    for arg in args:
        parser.add_argument(*arg.args, **arg.kwargs)

    if len(argv) >= 2:          # doit_utc a_task [args]
        if argv[1] == name:
            sargv = argv[2:]
            return parser.parse_args(sargv)
        else:
            sargv = argv[2:]
            try:
                args = parser.parser_args(sargv)
                return args
            except BaseException as e:
                raise Exception(e.args)
    else:
        raise Exception("Wrong number of arguments in sys.argv")


def argument(*args, **kwargs):
    return SimpleNamespace(args=args, kwargs=kwargs)


def selected_uv(all=False):
    if all:
        for planning, settings0 in settings.PLANNINGS.items():
            uvp = settings0['UVS']
            for uv in uvp:
                yield planning, uv, {'planning': planning, 'uv': uv}
    else:
        for planning, settings0 in settings.PLANNINGS.items():
            uvp = settings0['UVS']
            for uv in set(settings.SELECTED_UVS).intersection(set(uvp)):
                yield planning, uv, {'planning': planning, 'uv': uv}


def get_unique_uv():
    uvs = list(selected_uv())
    if len(uvs) != 1:
        uvs = [uv for _, uv, _ in uvs]
        raise Exception(f"Une seule UV doit être sélectionnée. Les UVs sélectionnées sont: {', '.join(uvs)}")
    return uvs[0]


def documents(fn, **info):
    if "local" in info:
        base_dir = os.path.basename(settings.BASE_DIR)
    else:
        base_dir = settings.BASE_DIR

    if 'uv' in info or 'ue' in info:
        uv = info.get('uv', info.get('ue'))
        return os.path.join(base_dir, uv, 'documents', fn)
    else:
        return os.path.join(base_dir, 'documents', fn)


def generated(fn, **info):
    if "local" in info:
        base_dir = ""
    else:
        base_dir = settings.BASE_DIR

    if 'uv' in info or 'ue' in info:
        uv = info.get('uv', info.get('ue'))
        return os.path.join(base_dir, uv, 'generated', fn)
    else:
        return os.path.join(base_dir, 'generated', fn)


def add_templates(**templates):
    def decorator(func):
        for key, value in templates.items():
            setattr(func, key, value)
        return func
    return decorator


def hexxor(a, b):  # xor two hex strings of the same length
    return "".join(["%x" % (int(x, 16) ^ int(y, 16)) for (x, y) in zip(a, b)])


def md5(fname):
    hash_md5 = hashlib.md5()
    hash_md5.update(fname.encode('utf8'))
    return hash_md5.hexdigest()


def hash_rot_md5(a):
    def substring():
        b = a + a
        for i in range(len(a)):
            yield b[i : (i + len(a))]

    s0 = "0" * len(a)
    s0 = md5(s0)
    for s in substring():
        s0 = hexxor(s0, md5(s))

    return s0


def aggregate(left_on, right_on, preprossessing=None, postprocessing=None, sanitizer=None, subset=None, drop=None, rename=None, read_method=None, kw_read={}):
    def aggregate0(df, path):
        nonlocal sanitizer

        # Check that left_on column exists
        check_columns(df, left_on)

        # Infer a read method if not provided
        if read_method is None:
            if path.endswith('.csv'):
                dff = pd.read_csv(path, **kw_read)
            elif path.endswith('.xlsx') or path.endswith('.xls'):
                dff = pd.read_excel(path, **kw_read)
            else:
                raise Exception('No read method and unsupported file extension')
        else:
            dff = read_method(path, **kw_read)

        # Preprocessing on data to be merged
        if preprossessing is not None:
            dff = preprossessing(dff)

        # Check that right_on column exists in data to be merged
        check_columns(dff, right_on)

        # Extract subset of columns, right_on included
        if subset is not None:
            dff = dff[list(set([right_on] + subset))]

        # Allow to drop columns, right_on not allowed
        if drop is not None:
            if right_on in drop:
                raise Exception('On enlève pas la clé')
            dff = dff.drop(drop, axis=1, errors='ignore')

        # Rename columns in data to be merged
        if rename is not None:
            if right_on in rename:
                raise Exception('Pas de renommage de la clé possible')
            dff = dff.rename(columns=rename)

        drop_cols = []
        if sanitizer is not None:
            if sanitizer == "slug_rot":
                def slug_rot_sanitizer(s):
                    s0 = unidecode.unidecode(s).lower()
                    s0 = ''.join(s0.split())
                    return hash_rot_md5(s0)
                sanitizer = slug_rot_sanitizer

            col_right_on = df[right_on]
            col_right_on_sanitized = col_right_on.apply(sanitizer)
            right_on_sanitized = right_on + "_sanitized"
            df[right_on_sanitized] = col_right_on_sanitized

            col_left_on = dff[left_on]
            col_left_on_sanitized = col_left_on.apply(sanitizer)
            left_on_sanitized = left_on + "_sanitized"
            dff[left_on_sanitized] = col_left_on_sanitized

            drop_cols += [left_on_sanitized, right_on_sanitized]
        else:
            left_on_sanitized = left_on
            right_on_sanitized = right_on
            if left_on != right_on:
                drop_cols += [right_on]
            else:
                drop_cols += [right_on + '_y']

        df = df.merge(dff, left_on=left_on_sanitized,
                      right_on=right_on_sanitized,
                      how='outer',
                      suffixes=('', '_y'),
                      indicator=True)

        # Select like how='left'
        df_left = df[df["_merge"].isin(['left_only', 'both'])]

        df_ro = df[df["_merge"] == 'right_only']
        if right_on in df_ro.columns:
            for index, row in df_ro.iterrows():
                print("WARNING:", row[right_on])
        elif right_on + "_y" in df_ro.columns:
            for index, row in df_ro.iterrows():
                print("WARNING:", row[right_on + '_y'])

        drop_cols += ['_merge']

        df = df_left.drop(drop_cols, axis=1, errors='ignore')

        if postprocessing is not None:
            df = postprocessing(df)

        return df

    return aggregate0


def skip_range(d1, d2):
    return [d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)]


def skip_week(d1, weeks=1):
    return [d1 + timedelta(days=x) for x in range(7*weeks-1)]


def action_msg(obj, **kwargs):
    if isinstance(obj, str):
        msg = obj
    else:
        msg = obj.__doc__
        msg = textwrap.fill(" ".join(msg.splitlines()[1:]).strip())

    action = {
        'actions': [lambda: TaskFailed(msg)],
        'verbosity': 2,
        'uptodate': [False]
    }

    action.update(**kwargs)

    return action


class KeepError(Exception):
    pass


def rel_to_dir(path, root):
    common_prefix = os.path.commonprefix([path, root])
    return os.path.relpath(path, common_prefix)


class Output():
    def __init__(self, target, protected=False):
        self.target = target
        self.protected = protected

    def __enter__(self):
        if os.path.exists(self.target):
            if self.protected:
                while True:
                    try:
                        choice = input('Le fichier `%s'' existe déjà. Écraser (d), garder (g), sauvegarder (s), annuler (a) ? ' % rel_to_dir(self.target, settings.BASE_DIR))
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
                print('Écrasement du fichier `%s\'' %
                      rel_to_dir(self.target, settings.BASE_DIR))
        else:
            dirname = os.path.dirname(self.target)
            if not os.path.exists(dirname):
                os.makedirs(dirname)

        return lambda: self.target

    def __exit__(self, type, value, traceback):
        if type is ZeroDivisionError:
            return True
        if type is None:
            print(f"Wrote `{rel_to_dir(self.target, settings.BASE_DIR)}'")


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

def create_cal_from_dataframe(df, text, target):
    """Crée un calendrier avec text dans les cases"""

    # 08:15 should be 8_15
    def convert_time(time):
        time = time.replace(':', '_')
        return re.sub('^0', '', time)

    def convert_day(day):
        mapping = {'Lundi': 'Lun',
                   'Mardi': 'Mar',
                   'Mercredi': 'Mer',
                   'Jeudi': 'Jeu',
                   'Vendredi': 'Ven',
                   'Samedi': 'Sam',
                   'Dimanche': 'Dim'}
        return mapping[day]

    def convert_author(author):
        parts = re.split('[ -]', author)
        return ''.join(e[0].upper() for e in parts)

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
        return rf'\node[2hours, {half}, {ctype}] at ({day}-{bh}) {{{text}}};'

    blocks = []
    for hour, group in df.groupby(['Jour', 'Heure début', 'Heure fin']):
        if len(group) > 2:
            raise Exception("Trop de créneaux en même temps")
        elif len(group) == 2:
            group = group.sort_values('Semaine')
            block1 = build_block(group.iloc[0], text, half='atleft')
            block2 = build_block(group.iloc[1], text, half='atright')
            blocks += [block1, block2]
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

        return days

    beg = settings.PLANNINGS[planning_type]['PL_BEG']
    end = settings.PLANNINGS[planning_type]['PL_END']

    planning_C = generate_days(beg, end, settings.SKIP_DAYS_C, settings.TURN, 'C')
    planning_D = generate_days(beg, end, settings.SKIP_DAYS_D, settings.TURN, 'D')
    planning_T = generate_days(beg, end, settings.SKIP_DAYS_T, settings.TURN, 'T')

    return {
        'C': planning_C,
        'D': planning_D,
        'T': planning_T
    }


def ical_events(dataframe):
    """Retourne les évènements iCal de tous les cours trouvés dans DATAFRAME"""

    from pytz import timezone
    localtz = timezone('Europe/Paris')

    def timestamp(row):
        d = row['date']
        hm = row['Heure début'].split(':')
        h = int(hm[0])
        m = int(hm[1])
        return datetime(year=d.year, month=d.month, day=d.day, hour=h, minute=m)

    ts = dataframe.apply(timestamp, axis=1)
    dataframe = dataframe.assign(timestamp=ts.values)
    df = dataframe.sort_values('timestamp')

    cal = Calendar()
    cal['summary'] = settings.SEMESTER

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


def compute_slots(csv_inst_list, planning_type, empty_instructor=True, filter_uvs=None):
    df = pd.read_csv(csv_inst_list)
    df = df.loc[df['Planning'] == planning_type]

    if not empty_instructor:
        df = df.loc[(~pd.isnull(df['Intervenants']))]
    if filter_uvs:
        df = df.loc[df['Code enseig.'].isin(filter_uvs)]

    planning = create_plannings(planning_type)

    planning_C = planning['C']
    pl_C = pd.DataFrame(planning_C)
    pl_C.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

    df_C = df.loc[df['Lib. créneau'].str.startswith('C'), :]
    df_Cm = pd.merge(df_C, pl_C, how='left', left_on='Jour', right_on='dayname')

    planning_D = planning['D']
    pl_D = pd.DataFrame(planning_D)
    pl_D.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

    df_D = df.loc[df['Lib. créneau'].str.startswith('D'), :]
    df_Dm = pd.merge(df_D, pl_D, how='left', left_on='Jour', right_on='dayname')

    planning_T = planning['T']
    pl_T = pd.DataFrame(planning_T)
    pl_T.columns = ['date', 'dayname', 'semaine', 'num', 'numAB', 'nweek']

    df_T = df.loc[df['Lib. créneau'].str.startswith('T'), :]
    if df_T['Semaine'].hasnans:
        df_Tm = pd.merge(df_T, pl_T, how='left', left_on='Jour', right_on='dayname')
    else:
        df_Tm = pd.merge(df_T, pl_T, how='left', left_on=['Jour', 'Semaine'], right_on=['dayname', 'semaine'])

    dfm = pd.concat([df_Cm, df_Dm, df_Tm], ignore_index=True)
    return dfm


def lib_list(lib):
    m = re.match('([CDT])([0-9]*)([AB]*)', lib)
    crs = {'C': 0, 'D': 1, 'T': 2}[m.group(1)]
    no = int('0' + m.group(2))
    sem = 0 if m.group(3) == 'A' else 1
    return crs, no, sem

