"""
Fichier qui regroupe des tâches de génération de fichiers ICal des
créneaux d'une UV ou d'un intervenant.
"""

import os
import glob
import tempfile
import zipfile
import datetime
import pytz
from icalendar import Event, Calendar
import numpy as np
import pandas as pd

from ..utils_config import Output, compute_slots
from ..utils import argument
from .instructors import AddInstructors
from .base import CliArgsMixin, TaskBase


def ical_events(dataframe, **settings):
    """Retourne les évènements iCal de tous les cours trouvés dans DATAFRAME"""

    def timestamp(row):
        d = row["date"]
        hm = row["Heure début"].split(":")
        h = int(hm[0])
        m = int(hm[1])
        timetuple = (d.year, d.month, d.day, h, m)
        local_tz = pytz.timezone("Europe/Paris")
        return datetime.datetime(*timetuple).astimezone(local_tz).astimezone(pytz.utc)

    ts = dataframe.apply(timestamp, axis=1)
    dataframe = dataframe.assign(timestamp=ts)
    df = dataframe.sort_values("timestamp")

    cal = Calendar()
    cal["summary"] = settings["SEMESTER"]

    for index, row in df.iterrows():
        event = Event()

        uv = row["Code enseig."]
        name = row["Lib. créneau"].replace(" ", "")
        week = row["Semaine"]
        num = row["num"]
        activity = row["Activité"]
        numAB = row["numAB"]

        if week is not np.nan:
            summary = f"{uv} {activity}{numAB} {week}"
        else:
            summary = f"{uv} {activity}{num}"

        room_raw = row["Locaux"]
        if isinstance(room_raw, str):
            room = room_raw.replace(" ", "").replace("BF", "F")
            event.add("location", f"{room}")

        event.add("summary", summary)

        dt = row["timestamp"]
        event.add("dtstart", dt)
        event.add("dtend", dt + datetime.timedelta(hours=2))

        cal.add_component(event)

    return cal.to_ical(sorted=True)


class IcalInst(CliArgsMixin, TaskBase):
    """Fichier iCal de tous les créneaux par intervenant

    Crée un fichier iCal de tous les créneaux de Cours/TP/TD du ou des
    plannings renseignés pour les intervenants renseignés.
    """

    target_dir = "generated"
    target_name = "{name}_ics.zip"
    always_make = True

    cli_args = (
        argument(
            "-p",
            "--plannings",
            nargs="+",
            help="Liste des plannings à considérer",
        ),
        argument(
            "-i",
            "--insts",
            nargs="+",
            help="Liste des intervenants à considérer (all pour tous les intervenants)",
        ),
    )

    def setup(self):
        super().setup()
        self.csv_slot_inst = AddInstructors.target_from()
        self.file_dep = [self.csv_slot_inst]
        if self.plannings is None:
            self.plannings = self.settings.SELECTED_PLANNINGS
        self.target = self.build_target(name=f"{'_'.join(self.plannings)}")
        if self.insts is None:
            self.insts = [self.settings.DEFAULT_INSTRUCTOR]

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
            settings = {
                "SEMESTER": self.settings.SEMESTER
            }
            if len(self.insts) == 1:
                inst = self.insts[0]
                dfm_inst = dfm.loc[dfm["Intervenants"].astype(str) == inst, :]
                output = self.build_target(
                    name=f'{inst.replace(" ", "_")}',
                    plannings=f"{'_'.join(self.plannings)}",
                    target_name="{name}_{plannings}.ics"
                )
                events = ical_events(dfm_inst, **settings)
                with Output(output) as output:
                    with open(output(), "wb") as fd:
                        fd.write(events)
            else:
                temp_dir = tempfile.mkdtemp()
                for inst in self.insts:
                    dfm_inst = dfm.loc[dfm["Intervenants"].astype(str) == inst, :]
                    events = ical_events(dfm_inst, **settings)

                    output = f'{inst.replace(" ", "_")}.ics'
                    with open(os.path.join(temp_dir, output), "wb") as fd:
                        fd.write(events)

                with Output(self.target) as output0:
                    with zipfile.ZipFile(output0(), "w") as z:
                        for filepath in glob.glob(os.path.join(temp_dir, "*.ics")):
                            z.write(filepath, os.path.basename(filepath))

        else:
            unknown = set(self.insts).difference(all_insts)
            raise Exception(f"Intervenant(s) inconnu(s): {', '.join(unknown)}, intervenant(s) enregistré(s): {', '.join(all_insts)}")
