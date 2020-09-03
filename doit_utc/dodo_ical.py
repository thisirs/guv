"""
Fichier qui regroupe des tâches de génération de fichiers ICal des
créneaux d'une UV ou d'un intervenant.
"""

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
from .utils_config import Output, generated, compute_slots
from .utils import argument
from .dodo_instructors import task_add_instructors
from .tasks import UVTask, CliArgsMixin


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


class IcalInst(UVTask, CliArgsMixin):
    """Fichier iCal de tous les créneaux des intervenants

    Crée un fichier iCal de tous les créneaux de Cours/TP/TD du ou des
    plannings renseignés pour les intervenants renseignés.
    """

    always_make = True

    cli_args = (
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

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.csv_slot_inst = generated(task_add_instructors.target)
        self.file_dep = [self.csv_slot_inst]
        self.target = generated(f"{'_'.join(self.plannings)}_ics.zip")

    def run(self):
        tables = [
            compute_slots(self.csv_slot_inst, ptype, empty_instructor=False)
            for ptype in self.plannings
        ]
        dfm = pd.concat(tables)

        all_insts = dfm["Intervenants"].unique()
        if len(self.insts) == 1 and self.insts[0] == "all":
            self.insts = all_insts

        if set(self.insts).issubset(set(all_insts)):
            if len(self.insts) == 1:
                inst = self.insts[0]
                dfm_inst = dfm.loc[dfm["Intervenants"].astype(str) == inst, :]
                output = generated(f'{inst.replace(" ", "_")}.ics')
                events = ical_events(dfm_inst)
                with Output(output) as output:
                    with open(output(), "wb") as fd:
                        fd.write(events)
            else:
                temp_dir = tempfile.mkdtemp()
                for inst in self.insts:
                    dfm_inst = dfm.loc[dfm["Intervenants"].astype(str) == inst, :]
                    events = ical_events(dfm_inst)

                    output = f'{inst.replace(" ", "_")}.ics'
                    with open(os.path.join(temp_dir, output), "wb") as fd:
                        fd.write(events)

                with Output(self.target) as output0:
                    with zipfile.ZipFile(output0(), "w") as z:
                        for filepath in glob.glob(os.path.join(temp_dir, "*.ics")):
                            z.write(filepath, os.path.basename(filepath))

        else:
            unknown = set(self.insts).difference(all_insts)
            return TaskFailed(f"Intervenant(s) inconnu(s): {', '.join(unknown)}")
