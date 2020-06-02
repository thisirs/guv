import os
import glob
import tempfile
import zipfile
from datetime import datetime, timedelta
from icalendar import Event, Calendar
import numpy as np
import pandas as pd

from doit.exceptions import TaskFailed

from .config import settings
from .utils import (
    Output,
    generated,
    compute_slots,
    parse_args,
    argument,
    actionfailed_on_exception,
)
from .dodo_instructors import task_add_instructors


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


@actionfailed_on_exception
def task_ical_inst():
    """Fichier iCal de tous les créneaux des intervenants

    Crée un fichier iCal de tous les créneaux de Cours/TP/TD du ou des
    plannings renseignés pour les intervenants renseignés.
    """

    def create_ical_inst(insts, plannings, csv):
        tables = [
            compute_slots(csv, ptype, empty_instructor=False) for ptype in plannings
        ]
        dfm = pd.concat(tables)

        all_insts = dfm["Intervenants"].unique()
        if len(insts) == 1 and insts[0] == "all":
            insts = all_insts

        if set(insts).issubset(set(all_insts)):
            if len(insts) == 1:
                inst = insts[0]
                dfm_inst = dfm.loc[dfm["Intervenants"].astype(str) == inst, :]
                output = generated(f'{inst.replace(" ", "_")}.ics')
                events = ical_events(dfm_inst)
                with Output(output) as output:
                    with open(output(), "wb") as fd:
                        fd.write(events)
            else:
                temp_dir = tempfile.mkdtemp()
                for inst in insts:
                    dfm_inst = dfm.loc[dfm["Intervenants"].astype(str) == inst, :]
                    events = ical_events(dfm_inst)

                    output = f'{inst.replace(" ", "_")}.ics'
                    with open(os.path.join(temp_dir, output), "wb") as fd:
                        fd.write(events)

                output = generated(f"ics.zip")
                with Output(output) as output0:
                    with zipfile.ZipFile(output0(), "w") as z:
                        for filepath in glob.glob(os.path.join(temp_dir, "*.ics")):
                            z.write(filepath, os.path.basename(filepath))

        else:
            unknown = set(insts).difference(all_insts)
            return TaskFailed(f"Intervenant(s) inconnu(s): {', '.join(unknown)}")

    args = parse_args(
        task_ical_inst,
        argument(
            "-p",
            "--plannings",
            nargs="+",
            default=settings.SELECTED_PLANNINGS,
            help="Liste des plannings à considérer",
        ),
        argument(
            "-i",
            "--insts",
            nargs="+",
            default=[settings.DEFAULT_INSTRUCTOR],
            help="Liste des intervenants à considérer",
        ),
    )

    deps = [generated(task_add_instructors.target)]

    return {
        "actions": [(create_ical_inst, [args.insts, args.plannings, deps[0]])],
        "file_dep": deps,
        "uptodate": [False],
        "verbosity": 2,
    }
