"""
Ce module rassemble les tâches de génération de fichiers iCal des
créneaux d'une UV ou d'un intervenant.
"""

import datetime
import glob
import os
import re
import tempfile
import zipfile

import pandas as pd
import pytz
from icalendar import Calendar, Event

from ..utils import argument, convert_to_time, normalize_string, ps
from ..utils_config import Output
from .base import CliArgsMixin, SemesterTask, UVTask
from .internal import Planning, PlanningSlots, PlanningSlotsAll


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
            output = f'{normalize_string(name, type="file")}.ics'
            with open(os.path.join(temp_dir, output), "wb") as fd:
                fd.write(events)

        with Output(self.target) as out:
            with zipfile.ZipFile(out.target, "w") as z:
                for filepath in glob.glob(os.path.join(temp_dir, "*.ics")):
                    z.write(filepath, os.path.basename(filepath))


class IcalSlots(SemesterTask, CliArgsMixin):
    """Fichier iCal d'un ou plusieurs créneaux dans la semaine pour tout un planning.

    {options}

    Examples
    --------

    .. code:: bash

       guv ical_slots -n SY02 -p A2023 -s "Mardi 10:15" -c Cours

    """

    target_dir = "generated"
    target_name = "{name}_{planning}_{course}.ics"
    uptodate = False

    cli_args = (
        argument(
            "-n",
            "--name",
            required=False,
            default="slots",
            help="Identifiant utilisé dans le nom du fichier, par défaut %(default)s."
        ),
        argument(
            "-p",
            "--planning",
            required=True,
            help="Planning à utiliser pour construire les créneaux."
        ),
        argument(
            "-s",
            "--slots",
            required=True,
            nargs="+",
            help="Liste des créneaux pour lesquels construire un fichier iCal (format `Mardi 9:00`)"
        ),
        argument(
            "-t",
            "--template",
            default="Séance {num}",
            help="Modèle utilisé pour générer les titres des évènements iCal. Par défaut `%(default)s`. Les remplacements suivants sont disponibles : `{num}`, `{numAB}`, `{nweek}` et `{name}`."
        ),
        argument(
            "-c",
            "--course",
            choices=["Cours", "TD", "TP", "TPA", "TPB"],
            required=True,
            help="Type des créneaux."
        ),
    )

    def setup(self):
        super().setup()
        self.parse_args()
        self.planning_file = Planning.target_from(planning=self.planning)
        self.file_dep = [self.planning_file]
        self.target = self.build_target()

        if self.template is None:
            if self.course in ["TPA", "TPB"]:
                self.template = "Séance {num}, semaine {AB}"
            else:
                self.template = "Séance {num}"

    def parse_slots(self):
        parsed_slots = []
        for slot in self.slots:
            m = re.match(r"([Ll]undi|[Mm]ardi|[Mm]ercredi|[Jj]eudi|[Vv]endredi|[Ss]amedi)\s+([0-9]{,2}:[0-9]{2})", slot)
            if m is not None:
                day = m.group(1).capitalize()
                time = m.group(2)
                parsed_slots.append((day, time))
            else:
                raise Exception(f"Créneau `{slot}` non reconnu, utiliser le format \"Lundi 10:15\"")
        return parsed_slots

    def run(self):
        if self.planning not in self.settings.PLANNINGS:
            msg = ", ".join(f"`{p}`" for p in self.settings.PLANNINGS)
            raise Exception(f"Planning `{self.planning}` inconnu, plannings reconnus : {msg}")

        planning = pd.read_csv(self.planning_file)

        if self.course in ["TPA", "TPB"]:
            course = self.course[:2]
            week = self.course[2]
            planning = planning.loc[(planning["Activité"] == course) & (planning["Semaine"] == week)]
        else:
            planning = planning.loc[planning["Activité"] == self.course]

        cal = Calendar()
        cal["summary"] = self.settings["SEMESTER"]

        for day, time in self.parse_slots():
            planning_day = planning.loc[planning["Jour"] == day]

            for index, row in planning_day.iterrows():
                event = Event()

                summary = self.template.format(
                    num=row["num"],
                    AB=row["Semaine"],
                    nweek=row["nweek"],
                    name=self.name
                )
                event.add("summary", summary)

                local_tz = pytz.timezone("Europe/Paris")
                date = pd.to_datetime(row["date"]).date()
                time = convert_to_time(time)

                dt = datetime.datetime.combine(date, time).astimezone(local_tz).astimezone(pytz.utc)
                event.add("dtstart", dt)
                event.add("dtend", dt + datetime.timedelta(hours=2))

                cal.add_component(event)

        events = cal.to_ical(sorted=True)

        with Output(self.target) as out:
            with open(out.target, "wb") as fh:
                fh.write(events)


class IcalInst(SemesterTask, CliArgsMixin):
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
                name=normalize_string(inst, type="file_no_space"),
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

                output = f'{normalize_string(inst, type="file_no_space")}.ics'
                with open(os.path.join(temp_dir, output), "wb") as fd:
                    fd.write(events)

            with Output(self.target) as out:
                with zipfile.ZipFile(out.target, "w") as z:
                    for filepath in glob.glob(os.path.join(temp_dir, "*.ics")):
                        z.write(filepath, os.path.basename(filepath))
