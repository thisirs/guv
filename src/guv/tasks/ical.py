"""
Ce module rassemble les tâches de génération de fichiers iCal des
créneaux d'une UV ou d'un intervenant.
"""

import datetime
import glob
import os
import tempfile
import zipfile

import pytz
from icalendar import Calendar, Event

from ..utils import argument, ps
from ..utils_config import Output
from .base import CliArgsMixin, TaskBase, UVTask
from .utc import PlanningSlots, PlanningSlotsAll


def ical_events(dataframe, **settings):
    """Retourne les évènements iCal de tous les cours trouvés dans `dataframe`."""

    def timestamp(row):
        local_tz = pytz.timezone("Europe/Paris")
        return datetime.datetime.combine(row["date"], row["Heure début"]).astimezone(local_tz).astimezone(pytz.utc)

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

        if isinstance(week, str):
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


class IcalUv(UVTask):
    """Fichiers iCal de tous les créneaux sur le semestre."""

    target_dir = "documents"
    target_name = "ics.zip"
    unique_uv = False

    def setup(self):
        super().setup()
        self.planning_slots = PlanningSlots.target_from(**self.info)
        self.file_dep = [self.planning_slots]
        self.target = self.build_target()

    def run(self):
        df = PlanningSlots.read_target(self.planning_slots)
        df.insert(0, "Code enseig.", self.uv)
        df.insert(0, "Planning", self.planning)

        settings = {"SEMESTER": self.settings.SEMESTER}

        temp_dir = tempfile.mkdtemp()
        key = df["Lib. créneau"] + df["Semaine"].fillna("")
        for name, group in df.groupby(key):
            events = ical_events(group, **settings)
            output = f'{name}.ics'
            with open(os.path.join(temp_dir, output), "wb") as fd:
                fd.write(events)

        with Output(self.target) as out:
            with zipfile.ZipFile(out.target, "w") as z:
                for filepath in glob.glob(os.path.join(temp_dir, "*.ics")):
                    z.write(filepath, os.path.basename(filepath))


class IcalInst(TaskBase, CliArgsMixin):
    """Fichier iCal de tous les créneaux par intervenant.

    Crée un fichier iCal de tous les créneaux de Cours/TP/TD du ou des
    plannings renseignés pour les intervenants renseignés.

    {options}

    Examples
    --------

    .. code:: bash

       guv ical_inst --insts "Bob Arctor" "Winston Smith"

    """

    target_dir = "generated"
    target_name = "{name}_ics.zip"
    uptodate = True

    cli_args = (
        argument(
            "-i",
            "--insts",
            nargs="+",
            help="Liste des intervenants à inclure dans les fichiers iCal. Par défaut, ``DEFAULT_INSTRUCTOR`` est utilisé. Mettre ``all`` pour tous les intervenants.",
        ),
    )

    def setup(self):
        super().setup()
        self.planning_slots_all = PlanningSlotsAll.target_from()
        self.file_dep = [self.planning_slots_all]

        self.parse_args()
        if self.insts is None:
            self.insts = [self.settings.DEFAULT_INSTRUCTOR]
        name = "_".join(i.replace(" ", "_") for i in self.insts)
        self.target = self.build_target(name=name)

    def run(self):
        df = PlanningSlotsAll.read_target(self.planning_slots_all)

        all_insts = df["Intervenants"].dropna().unique()
        if len(self.insts) == 1 and self.insts[0] == "all":
            self.insts = all_insts

        if not set(self.insts).issubset(set(all_insts)):
            unknown = set(self.insts).difference(all_insts)
            plural = ps(len(unknown))
            all_insts = "Aucun" if len(all_insts) == 0 else ', '.join(all_insts)
            raise Exception(f"Intervenant{plural} inconnu{plural}: {', '.join(unknown)}, intervenant(s) enregistré(s): {all_insts}")

        settings = {
            "SEMESTER": self.settings.SEMESTER
        }

        if len(self.insts) == 1:
            inst = self.insts[0]
            df_inst = df.loc[df["Intervenants"].astype(str) == inst, :]
            target = self.build_target(
                name=inst.replace(" ", "_"),
                target_name="{name}.ics"
            )
            events = ical_events(df_inst, **settings)
            with Output(target) as out:
                with open(out.target, "wb") as fd:
                    fd.write(events)
        else:
            temp_dir = tempfile.mkdtemp()
            for inst in self.insts:
                df_inst = df.loc[df["Intervenants"].astype(str) == inst, :]
                events = ical_events(df_inst, **settings)

                output = f'{inst.replace(" ", "_")}.ics'
                with open(os.path.join(temp_dir, output), "wb") as fd:
                    fd.write(events)

            with Output(self.target) as out:
                with zipfile.ZipFile(out.target, "w") as z:
                    for filepath in glob.glob(os.path.join(temp_dir, "*.ics")):
                        z.write(filepath, os.path.basename(filepath))
