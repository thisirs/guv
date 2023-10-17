"""
Ce module rassemble les tâches pour interagir avec Moodle : création
de fichiers de groupes officiels de Cours/TD/TP où aléatoires
(binômes, trinômes par groupes) prêt à charger, descriptif de l'UV et
des intervenants sous forme de code HTML à copier-coller dans Moodle,
tableau des créneaux de l'UV sous forme de tableau HTML, création de
fichier Json pour copier-coller des restrictions d'accès en fonction
de l'appartenance à un groupe.
"""

import datetime as dt
import json
import math
import os
import pprint
import random
import shlex
import sys
import textwrap

import browser_cookie3
import jinja2
import markdown
import numpy as np
import pandas as pd
import pynliner
import requests
import yapf.yapflib.yapf_api as yapf
from bs4 import BeautifulSoup

import guv

from ..exceptions import InvalidGroups
from ..logger import logger
from ..scripts.moodle_date import CondDate, CondGroup, CondOr, CondProfil
from ..utils import (
    argument,
    score_codenames,
    split_codename,
    make_groups,
    pformat,
    sort_values,
)
from ..utils_config import Output, check_if_present, rel_to_dir
from .base import CliArgsMixin, TaskBase, UVTask
from .instructors import WeekSlotsDetails
from .students import XlsStudentDataMerge
from .utc import PlanningSlots

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"


class CsvGroups(UVTask, CliArgsMixin):
    """Fichiers csv de groupes présents dans ``effectifs.xlsx`` pour Moodle.

    Crée par défaut des fichiers csv des groupes de Cours/TD/TP pour
    chaque UV sélectionnée. Avec l'option ``-g``, on peut spécifier
    d'autres groupes à exporter sous Moodle.

    {options}

    Examples
    --------

    .. code:: bash

       guv csv_groups --groups Groupe_Projet

    """

    target_dir = "generated"
    target_name = "{ctype}_group_moodle.csv"

    cli_args = (
        argument(
            "-g",
            "--groups",
            nargs="+",
            default=["Cours", "TD", "TP", "singleton"],
            help="Liste des groupements à considérer via un nom de colonne. Par défaut, les groupements ``Cours``, ``TD``, ``TP`` et ``singleton`` sont utilisés.",
        ),
        argument(
            "-l",
            "--long",
            action="store_true",
            help="Utilise les noms de groupes de Cours/TD/TP au format long, c'est à dire \"TP1\" et \"TD1\" au lieu de \"T1\" et \"D1\""
        )
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.parse_args()
        self.targets = [
            self.build_target(ctype=ctype)
            for ctype in self.groups
        ]

    def run(self):
        df = XlsStudentDataMerge.read_target(self.xls_merge)

        for ctype, target in zip(self.groups, self.targets):
            if ctype == "singleton":
                dff = df[["Courriel", "Login"]]

                with Output(target) as out:
                    dff.to_csv(out.target, index=False, header=False)
            else:
                if check_if_present(
                    df,
                    ctype,
                    file=self.xls_merge,
                    base_dir=self.settings.SEMESTER_DIR,
                    errors="warning",
                ):
                    dff = df[["Login", ctype]]
                    if ctype in ["TP", "TD"] and self.long:
                        new_col = (
                            dff[ctype]
                            .str.replace("D([0-9]+)", r"TD\1", regex=True)
                            .replace("T([0-9]+)", r"TP\1", regex=True)
                        )

                        dff = dff.assign(**{ctype: new_col})

                    with Output(target) as out:
                        dff.to_csv(out.target, index=False, header=False)

        if "MOODLE_ID" in self.settings:
            id = str(self.settings.MOODLE_ID)
        else:
            id = "<MOODLE_ID>"

        url = f"https://moodle.utc.fr/local/userenrols/import.php?id={id}"

        logger.info(textwrap.dedent(f"""\

        Charger les groupes sur Moodle à l'adresse {url} en spécifiant :

        - Champ utilisateur: "Nom d'utilisateur"
        - Inscrire dans les groupes : "Oui"
        - Créer les groupes: "Oui" s'il ne sont pas déjà créés

        """))


class CsvGroupsGroupings(UVTask, CliArgsMixin):
    """Fichier csv de groupes et groupements à charger sur Moodle pour les créer.

    Il faut spécifier le nombre de groupes dans chaque groupement avec
    l'argument ``-g`` et le nombre de groupements dans
    ``-G``.

    Le nom des groupements est controlé par un modèle spécifié par
    l'argument ``-F`` (par défaut "D##_P1"). Les remplacements
    disponibles sont :

    - ## : remplacé par des nombres
    - @@ : remplacé par des lettres

    Le nom des groupes est controlé par un modèle spécifié par
    l'argument ``-f`` (par défaut "D##_P1_@"). Les remplacements
    disponibles sont :

    - # : remplacé par des nombres
    - @ : remplacé par des lettres

    {options}

    Examples
    --------

    .. code:: bash

       guv csv_groups_groupings -G 3 -F Groupement_P1 -g 14 -f D##_P1_@
       guv csv_groups_groupings -G 2 -F Groupement_D1 -g 14 -f D1_P##_@
       guv csv_groups_groupings -G 2 -F Groupement_D2 -g 14 -f D2_P##_@
       guv csv_groups_groupings -G 2 -F Groupement_D3 -g 14 -f D3_P##_@

    """

    target_dir = "generated"
    target_name = "groups_groupings.csv"
    cli_args = (
        argument(
            "-g",
            type=int,
            metavar="N_GROUPS",
            dest="ngroups",
            required=True,
            help="Nombre de groupes dans chaque groupement",
        ),
        argument(
            "-f",
            dest="ngroupsf",
            metavar="FORMAT",
            default="D##_P1_@",
            help="Format du nom de groupe (par défaut: %(default)s)",
        ),
        argument(
            "-G",
            dest="ngroupings",
            metavar="N_GROUPINGS",
            type=int,
            required=True,
            help="Nombre de groupements différents",
        ),
        argument(
            "-F",
            dest="ngroupingsf",
            metavar="FORMAT",
            default="D##_P1",
            help="Format du nom de groupement (par défaut: %(default)s)",
        ),
    )

    def setup(self):
        super().setup()
        self.target = self.build_target(**self.info)
        self.parse_args()

    def run(self):
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ngroupings = min(26, self.ngroupings)
        ngroups = min(26, self.ngroups)

        groups = []
        groupings = []
        for G in range(ngroupings):
            grouping_letter = letters[G]
            grouping_number = str(G + 1)
            grouping = (self.ngroupingsf
                        .replace("@@", grouping_letter)
                        .replace("##", grouping_number))
            for g in range(ngroups):
                group_letter = letters[g]
                group_number = str(g + 1)
                group = (self.ngroupsf
                         .replace("@@", grouping_letter)
                         .replace("##", grouping_number)
                         .replace("@", group_letter)
                         .replace("#", group_number))

                groups.append(group)
                groupings.append(grouping)

        df_groups = pd.DataFrame({"groupname": groups, 'groupingname': groupings})
        with Output(self.target, protected=True) as out:
            df_groups.to_csv(out.target, index=False)


class HtmlInst(UVTask):
    """Génère la description des intervenants pour Moodle.

    Crée le fichier ``intervenants.html`` qui peut être utilisé dans
    Moodle pour afficher une description de l'équipe pédagogique avec
    les créneaux assurés.
    """

    target_dir = "generated"
    target_name = "intervenants.html"
    uptodate = False

    def setup(self):
        super().setup()
        self.week_slots_details = WeekSlotsDetails.target_from(**self.info)
        self.target = self.build_target()
        self.file_dep = [self.week_slots_details]

    def run(self):
        df = WeekSlotsDetails.read_target(self.week_slots_details)
        df["Name"] = df["Lib. créneau"] + df["Semaine"].fillna("")

        def format_slot_list(slots):
            return ", ".join(sorted(slots, key=split_codename))

        def format_start(day, start, week):
            start = start.strftime("%Hh%M")
            start = start.replace("h00", "h").lstrip("0")
            if not pd.isnull(week):
                return f"{day[:3]}. {week} {start}"
            else:
                return f"{day[:3]}. {start}"

        def format_room(room):
            return (
                room.replace("BF A ", "FA")
                .replace("CR B", "Bessel")
                .replace("BF B ", "FB")
            )

        def sort_groups(groups):
            def sorter(elt):
                name, group = elt
                not_manager = 1 - int(any(group["Responsable"]))
                return (not_manager, score_codenames(group["Name"]))
            return sorted(groups, key=sorter)

        context = {
            "slots": [
                {
                    "name": row["Name"],
                    "instructor": {
                        "name": row["Intervenants"],
                        "email": row["Email"],
                    },
                    "is_manager": row["Responsable"],
                    "room": format_room(row["Locaux"]),
                    "start": format_start(*row[["Jour", "Heure début", "Semaine"]]),
                }
                for _, row in df.iterrows()
            ],
            "instructors": [
                {
                    "name": name,
                    "email": group.iloc[0]["Email"],
                    "slot_list": format_slot_list(group["Name"]),
                    "is_manager": not all(pd.isnull(group["Responsable"])),
                    "slots": [
                        {
                            "name": row["Name"],
                            "room": format_room(row["Locaux"]),
                            "start": format_start(*row[["Jour", "Heure début", "Semaine"]]),
                        }
                        for _, row in group.iterrows()
                    ]
                }
                for name, group in sort_groups(df.groupby("Intervenants"))
            ]
        }

        tmpl_dir = os.path.join(guv.__path__[0], "templates")
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
        def display_name(instructor):
            if instructor.get("email", None):
                return f'[{instructor["name"]}](mailto:{instructor["email"]})'
            else:
                return instructor["name"]

        env.filters["display_name"] = display_name
        template = env.get_template("instructors2.html.jinja2")
        md = template.render(**context)
        html = markdown.markdown(md)

        with Output(self.target, protected=True) as out:
            with open(out.target, "w") as fd:
                fd.write(html)


class HtmlTable(UVTask, CliArgsMixin):
    """Table HTML des Cours/TD/TP à charger sur Moodle

    Permet de générer des fragments HTML à coller dans une page Moodle
    qui décrivent sous forme de tableau l'ensemble des créneaux de
    Cours/TD/TP.

    {options}

    Examples
    --------

    .. code:: bash

       guv html_table --courses TP --num-AB
       guv html_table --grouped

    """

    target_dir = "generated"
    target_name = "{name}{AB}_table.html"
    uptodate = False

    cli_args = (
        argument(
            "-c",
            "--courses",
            nargs="*",
            default=["Cours", "TD", "TP"],
            help="Liste des types de créneaux pour lequel faire un tableau. Par défaut des tableaux sont créés pour les Cours, TD et TP.",
        ),
        argument(
            "-g",
            "--grouped",
            action="store_true",
            help="Grouper les cours dans le même tableau ou faire des fichiers distincts.",
        ),
        argument(
            "-a",
            "--num-AB",
            action="store_true",
            help="Permet de préciser si la numérotation des séances dans le tableau doit être en semaine A/B (A1, B1, A2, B2,...) ou normal (1, 2, 3, 4,...). Valable uniquement pour les TP. Pour les autres types la numérotation classique est toujours utilisée.",
        ),
        argument(
            "-n",
            "--names",
            nargs="+",
            help="Liste ou fichier contenant les intitulés des cours à la place de ``C1``, ``C2``,...",
        ),
        argument(
            "--header-row-format",
            default="{beg}--{end}",
            help="Format pour l'en-tête de chaque ligne"
        )
    )

    def setup(self):
        super().setup()
        self.planning_slots = PlanningSlots.target_from(**self.info)
        self.file_dep = [self.planning_slots]

        self.parse_args()
        AB = "_TP_AB" if self.num_AB else ""
        if self.grouped:
            name = "_".join(self.courses) + "_grouped"
            self.target = self.build_target(name=name, AB=AB)
        else:
            self.targets = [
                self.build_target(name=course, AB=AB)
                for course in self.courses
            ]

    def write_html_table(self, target, html):
        # Inline style for Moodle
        output = pynliner.fromString(html)

        with Output(target, protected=True) as out:
            with open(out.target, "w") as fd:
                fd.write(output)

    def run(self):
        if self.names is not None and len(self.names) == 1:
            if not os.path.exists(self.names[0]):
                raise Exception("Le fichier `{self.names[0]}` n'existe pas")
            with open(self.names[0], "r") as fd:
                self.names = [l.strip() for l in fd.readlines()]

        if self.grouped:
            html = self.get_html(self.courses)
            self.write_html_table(self.target, html)
        else:
            for course, target in zip(self.courses, self.targets):
                html = self.get_html([course])
                self.write_html_table(target, html)

    def get_html(self, courses):
        """Return html-rendered tables of all COURSES"""

        # Get Pandas dataframe
        df = self.get_table(courses)

        # Replace NaN
        df = df.fillna("—")

        dfs = df.style
        dfs = (
            dfs.set_table_styles(
                [
                    dict(selector="th.row_heading", props=[("width", "100px")]),
                    dict(
                        selector="th",
                        props=[("font-size", "small"), ("text-align", "center")],
                    ),
                ]
            )
            .set_properties(
                **{"width": "50px", "text-align": "center", "valign": "middle"}
            )
            .set_table_attributes('align="center" cellspacing="10" cellpadding="2"')
        )

        return dfs.to_html()

    def get_table(self, courses):
        """Get a Pandas DataFrame from all COURSES"""

        # Select wanted slots
        slots = PlanningSlots.read_target(self.planning_slots)
        slots = slots[slots["Activité"].isin(courses)]

        if len(slots) == 0:
            raise Exception("Pas de créneaux pour ", courses)

        def mondays(beg, end):
            while beg <= end:
                nbeg = beg + dt.timedelta(days=7)
                yield beg, nbeg
                beg = nbeg

        def merge_slots(df):
            activity = df.iloc[0]["Activité"]

            def to_names(num):
                if self.names is not None:
                    return str(self.names[num - 1])
                else:
                    return str(num)

            if activity == "Cours":
                return ", ".join(df.num.apply(to_names))
            elif activity == "TD" or (activity == "TP" and not self.num_AB):
                return ", ".join(df["num"].astype("string"))
            else:
                return ", ".join(df.Semaine + df.numAB.str)

        # Iterate on each week of semester
        rows = []
        weeks = []
        for (mon, nmon) in mondays(
            self.settings.PLANNINGS[self.planning]["PL_BEG"],
            self.settings.PLANNINGS[self.planning]["PL_END"],
        ):
            weeks.append(
                "{}-{}".format(
                    mon.strftime("%d/%m"), (nmon - dt.timedelta(days=1)).strftime("%d/%m")
                )
            )

            # Select slots on current week
            cr_week = slots.loc[(slots.date >= mon) & (slots.date < nmon)]
            if len(cr_week) > 0:
                e = cr_week.groupby("Lib. créneau").apply(merge_slots)
                rows.append(e)
            else:
                rows.append(pd.Series(dtype="object"))

        # Weeks on rows
        df = pd.concat(rows, axis=1, sort=True).transpose()

        # Reorder columns
        if len(df.columns) > 1:
            cols = sorted(df.columns.tolist(), key=split_codename)
            df = df[cols]

        # Give name to indexes
        df.columns.name = "Séance"
        df.index = weeks
        df.index.name = "Semaine"

        return df


class JsonRestriction(UVTask, CliArgsMixin):
    """Fichier json de restrictions d'accès aux ressources Moodle basées sur le début/fin des séances

    Le fichier json contient des restrictions d'accès pour les
    créneaux de Cours/TD/TP basé sur l'appartenance aux groupes de
    Cours/TD/TP, sur les début/fin de séance, début/fin de semaine.

    Le fragment json peut être transféré sous Moodle en tant que
    restriction d'accès grâce au script Greasemonkey disponible
    :download:`ici <../resources/moodle_availability_conditions.js>`.

    Pour les contraintes par créneaux qui s'appuie sur l'appartenance
    à un groupe, il est nécessaire de renseigner la variable
    ``MOODLE_GROUPS`` dans le fichier ``config.py`` qui relie le nom
    des groupes de Cours/TD/TP dans le fichier ``effectif.xlsx`` aux
    identifiants Moodle correspondant (voir la tâche
    :class:`~guv.tasks.moodle.FetchGroupId` pour récupérer la correspondance).

    L'argument ``-c`` permet de spécifier les activités considérées, à
    choisir parmi Cours, TD ou TP.

    Le drapeau ``-a`` permet de grouper les séances par deux semaines
    dans le cas où il y a des semaines A et B. La fin d'une activité
    est alors identifiée à la fin de la semaine B.

    Les restrictions globales implémentées sont les suivantes :

    - antérieur à la date du premier créneau
    - postérieur à la date du premier créneau
    - postérieur à la date du premier créneau moins 3 jours
    - postérieur à la date du dernier créneau
    - antérieur à la date du dernier créneau
    - postérieur au lundi précédant immédiatement le premier créneau
    - postérieur au vendredi suivant immédiatement le dernier créneau
    - postérieur à minuit juste avant le premier créneau
    - postérieur à minuit juste après le dernier créneau

    Les restrictions dépendant de l'appartenance à un groupe sont les
    suivantes :

    - antérieur à la date de début de créneau de l'étudiant
    - postérieur à la date de début de créneau de l'étudiant
    - postérieur à la date de fin de créneau de l'étudiant
    - antérieur à la date de fin de créneau de l'étudiant
    - restreint à la séance de l'étudiant
    - restreint à la séance de l'étudiant plus 15 minutes après
    - restreint au début de la séance, 3 minutes avant, 5 minutes après

    {options}

    """

    target_dir = "generated"
    target_name = "moodle_restrictions_{course}{AB}.json"
    uptodate = False

    cli_args = (
        argument(
            "-c",
            "--course",
            required=True,
            help="Type de séances considérées parmi ``Cours``, ``TD`` ou ``TP``.",
        ),
        argument(
            "-a",
            "--num-AB",
            action="store_true",
            help="Permet de prendre en compte les semaines A/B. Ainsi, la fin d'une séance est à la fin de la semaine B.",
        ),
        argument(
            "-l",
            "--long",
            action="store_true",
            help="Utilise les noms de groupes de Cours/TD/TP au format long, c'est à dire \"TP1\" et \"TD1\" au lieu de \"T1\" et \"D1\""
        ),
        argument(
            "-v",
            "--visible",
            action="store_true",
            help="Rend les restrictions visibles des étudiants"
        )
    )

    def setup(self):
        super().setup()
        self.planning_slots = PlanningSlots.target_from(**self.info)
        self.file_dep = [self.planning_slots]

        self.parse_args()
        AB = "_AB" if self.num_AB else ""
        self.target = self.build_target(AB=AB)

    def run(self):
        df = PlanningSlots.read_target(self.planning_slots)
        available_courses = df["Activité"].unique()

        if self.course not in available_courses:
            raise Exception(
                "Aucun créneau de type `%s`. Choisir parmi %s"
                % (self.course, ", ".join(f"`{c}`" for c in available_courses))
            )

        df_c = df.loc[df["Activité"] == self.course]

        # Maybe rename T1A, D1 into TP1A, TD1
        if self.long:
            new_col = (
                df_c["Lib. créneau"]
                .str.replace("D([0-9]+)", r"TD\1", regex=True)
                .replace("T([0-9]+)", r"TP\1", regex=True)
            )

            df_c = df_c.assign(**{"Lib. créneau": new_col})

        visible = self.visible

        key = "numAB" if self.num_AB else "num"
        gb = df_c.groupby(key)

        if "MOODLE_GROUPS" not in self.settings or not self.settings.MOODLE_GROUPS:
            logger.warning(
                "La variable `MOODLE_GROUPS` n'est pas spécifiée (voir tâche `FetchGroupId`). "
                "Elle est nécessaire pour avoir des contraintes liées aux groupes Moodle"
            )

        def get_beg_end_date_each(num, df):
            def group_beg_end(row):
                if self.num_AB:
                    group = row["Lib. créneau"] + row["Semaine"]
                else:
                    group = row["Lib. créneau"]

                hd = dt.datetime.combine(row["date"], row["Heure début"])
                hf = dt.datetime.combine(row["date"], row["Heure fin"])

                return group, hd, hf

            gbe = [group_beg_end(row) for index, row in df.iterrows()]
            dt_min = min(b for g, b, e in gbe)
            dt_min3 = dt_min - dt.timedelta(days=3)
            dt_max = max(e for g, b, e in gbe)

            dt_min_monday = dt_min - dt.timedelta(days=dt_min.weekday())
            dt_min_monday = dt.datetime.combine(dt_min_monday, dt.time.min)
            dt_min_midnight = dt.datetime.combine(dt_min, dt.time.min)

            if len(gbe) > 1:
                after_beg_group = [
                    (CondGroup(visible=visible) == g) & (CondDate(visible=visible) >= b) for g, b, e in gbe
                ]
                before_beg_group = [
                    (CondGroup(visible=visible) == g) & (CondDate(visible=visible) < b) for g, b, e in gbe
                ]

            dt_max_friday = dt_max + dt.timedelta(days=6 - dt_max.weekday())
            dt_max_friday = dt.datetime.combine(dt_max_friday, dt.time.max)
            dt_max_midnight = dt.datetime.combine(dt_max, dt.time.max)

            no_group = {
                "accessible si: t < min(B)": (CondDate(visible=visible) < dt_min).to_PHP(),
                "accessible si: t >= min(B)": (CondDate(visible=visible) >= dt_min).to_PHP(),
                "accessible si: t >= min(B)-3days": (CondDate(visible=visible) >= dt_min3).to_PHP(),
                "accessible si: t >= max(E)": (CondDate(visible=visible) >= dt_max).to_PHP(),
                "accessible si: t < max(E)": (CondDate(visible=visible) < dt_max).to_PHP(),
                "accessible si: t >= previous_monday(min(B))": (CondDate(visible=visible) >= dt_min_monday).to_PHP(),
                "accessible si: t >= next_friday(max(E))": (CondDate(visible=visible) >= dt_max_friday).to_PHP(),
                "accessible si: t >= previous_midnight(min(B))": (CondDate(visible=visible) >= dt_min_midnight).to_PHP(),
                "accessible si: t >= next_midnight(max(E))": (CondDate(visible=visible) >= dt_max_midnight).to_PHP(),
                "accessible si: min(B) <= t < min(B) + 20mins": ((CondDate(visible=visible) >= dt_min) & (CondDate(visible=visible) < dt_min + dt.timedelta(minutes=20))).to_PHP()
            }

            if len(gbe) > 1:
                after_end_group = [
                    CondOr([CondGroup(visible=visible) == g]) & (CondDate(visible=visible) >= e) for g, b, e in gbe
                ]
                before_end_group = [
                    CondOr([CondGroup(visible=visible) == g]) & (CondDate(visible=visible) < e) for g, b, e in gbe
                ]

                def window_group_start(g, b, e, p=0, q=0):
                    return CondOr([(CondGroup(visible=visible) == g)]) & (CondDate(visible=visible) >= b + dt.timedelta(minutes=p)) & (CondDate(visible=visible) < b + dt.timedelta(minutes=q))

                def window_group(g, b, e, p=0, q=0):
                    return CondOr([(CondGroup(visible=visible) == g)]) & (CondDate(visible=visible) >= b + dt.timedelta(minutes=p)) & (CondDate(visible=visible) < e + dt.timedelta(minutes=q))

                def windows(func, gbe, p=0, q=0):
                    return [
                        func(g, b, e, p, q) for g, b, e in gbe
                    ]

                if "MOODLE_GROUPS" in self.settings and self.settings.MOODLE_GROUPS:
                    info = dict(groups=self.settings.MOODLE_GROUPS)
                    no_group.update({
                        "accessible si: t <= B par groupe": CondOr(before_beg_group).to_PHP(**info),
                        "accessible si: t > B par groupe": CondOr(after_beg_group).to_PHP(**info),
                        "accessible si: t > E par groupe": CondOr(after_end_group).to_PHP(**info),
                        "accessible si: t <= E par groupe": CondOr(before_end_group).to_PHP(**info),
                        "accessible si: B <= t < E par groupe": CondOr(windows(window_group, gbe)).to_PHP(**info),
                    })
                    for p, q in ((-3, 5),):
                        rst = CondOr(windows(window_group_start, gbe, p, q))
                        no_group[f"accessible si: B + {p}min <= t < B + {q}min par groupe"] = rst.to_PHP(**info)

                    for p, q in ((0, 15),):
                        no_group[f"accessible si: B + {p}min <= t < E + {q}min par groupe"] = CondOr(windows(window_group, gbe, p, q)).to_PHP(**info)

                    for p, q in ((0, 30),):
                        no_group[f"accessible si: B + {p}min <= t < B + {q}min par groupe"] = CondOr(windows(window_group_start, gbe, p, q)).to_PHP(**info)

            session = f"Séance {num} : {dt_min_monday.strftime('%d-%m-%Y')} -- {dt_max_friday.strftime('%d-%m-%Y')}"

            return session, no_group

        moodle_date = dict(get_beg_end_date_each(name, g) for name, g in gb)
        max_len = max(len(s) for s in list(moodle_date.values())[0])
        with Output(self.target, protected=True) as out:
            with open(out.target, "w") as fd:
                s = (
                    "{\n"
                    + ",\n".join(
                        (
                            f'  "{slot}": {"{"}\n'
                            + ",\n".join(
                                (
                                    f'    "{name}": {" " * (max_len - len(name))}'
                                    + json.dumps(moodle_json, ensure_ascii=False)
                                )
                                for name, moodle_json in dates.items()
                            )
                            + "\n  }"
                            for slot, dates in moodle_date.items()
                        )
                    )
                    + "\n}"
                )
                print(s, file=fd)


class JsonGroup(UVTask, CliArgsMixin):
    """Fichier json des restrictions d'accès aux ressources sur Moodle par adresse courriel

    Le fichier Json contient des restrictions d'accès à copier dans
    Moodle. L'argument ``group`` permet de construire des restrictions
    par groupe. L'intérêt par rapport à une restriction classique à
    base d'appartenance à un groupe dans Moodle est qu'il n'est pas
    nécessaire de charger ce groupe sur Moodle et que l'étudiant ne
    peut pas savoir à quel groupe il appartient.

    {options}

    """

    target_dir = "generated"
    target_name = "{group}_group_moodle.json"
    cli_args = (
        argument(
            "-g",
            "--group",
            required=True,
            help="Nom de la colonne réalisant un groupement",
        ),
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target = self.build_target()

    def run(self):
        df = XlsStudentDataMerge.read_target(self.xls_merge)

        check_if_present(
            df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
        )
        dff = df[["Adresse de courriel", self.group]]

        # Dictionnary of group in GROUP and corresponding Cond
        # object for that group.
        json_dict = {
            group_name: CondOr(
                [
                    CondProfil("email") == row["Adresse de courriel"]
                    for index, row in group.iterrows()
                ]
            ).to_PHP()
            for group_name, group in dff.groupby(self.group)
        }

        with Output(self.target, protected=True) as out:
            with open(out.target, "w") as fd:
                s = (
                    "{\n"
                    + ",\n".join(
                        (
                            f'  "{group_name}": '
                            + json.dumps(json_string, ensure_ascii=False)
                            for group_name, json_string in json_dict.items()
                        )
                    )
                    + "\n}"
                )
                print(s, file=fd)


def get_coocurrence_matrix_from_array(series):
    """Return co-occurence matrix of a series as a Pandas dataframe."""
    one_hot = pd.get_dummies(series)
    return one_hot @ one_hot.T

def get_coocurrence_matrix_from_partition(groups, index):
    """Return co-occurence matrix from a partition of index."""
    N = sum(len(p) for p in groups)
    assert(N == len(index))

    A = pd.DataFrame(np.zeros((N, N), dtype=int), index=index, columns=index)
    for p in groups:
        A.loc[p, p] = 1
    return A

def get_coocurrence_dict(df, columns):
    """Return a dictionary mapping column with their coocurrence matrix."""
    cooc_dict = {}
    for column in columns:
        cooc = get_coocurrence_matrix_from_array(df[column])
        if column in cooc_dict:
            cooc_dict[column] = cooc_dict[column] + cooc
        else:
            cooc_dict[column] = cooc
    return cooc_dict


class CsvCreateGroups(UVTask, CliArgsMixin):
    """Création aléatoire de groupes d'étudiants prêt à charger sous Moodle.

    Cette tâche crée un fichier csv d'affectation des étudiants à un
    groupe directement chargeable sous Moodle. Si l'option
    ``--grouping`` est spécifiée les groupes sont créés à l'intérieur
    de chaque sous-groupe (de TP ou TD par exemple).

    Le nombre de groupes créés (au total ou par sous-groupes suivant
    ``--grouping``) est controlé par une des options mutuellement
    exclusives ``--proportions``, ``--group-size`` et
    ``--num-groups``. L'option ``--proportions`` permet de spécifier
    un nombre de groupes via une liste de proportions. L'option
    ``--group-size`` permet de spécifier la taille maximale de chaque
    groupe. L'option ``--num-groups`` permet de spécifier le nombre de
    sous-groupes désirés.

    Le nom des groupes est contrôlé par l'option ``--template``. Les
    remplacements suivants sont disponibles à l'intérieur de
    ``--template`` :

    - ``{title}`` : remplacé par le titre (premier argument)
    - ``{grouping_name}`` : remplacé par le nom du sous-groupe à
      l'intérieur duquel on construit des groupes (si on a spécifié
      ``--grouping``)
    - ``{group_name}`` : nom du groupe en construction (si on a
      spécifié ``--names``)
    - ``#`` : numérotation séquentielle du groupe en construction (si
      ``--names`` n'est pas spécifié)
    - ``@`` : lettre séquentielle du groupe en construction (si
      ``--names`` n'est pas spécifié)

    L'option ``--names`` peut être une liste de noms à utiliser ou un
    fichier contenant une liste de noms ligne par ligne. Il sont pris
    aléatoirement si on spécifie le drapeau ``--random``.

    Le drapeau ``--global`` permet de ne pas remettre à zéro la
    génération des noms de groupes lorsqu'on change le groupement à
    l'intérieur duquel on construit des groupes (utile seulement si on
    a spécifié ``--grouping``).

    Par défaut, la liste des étudiants est triée aléatoirement avant
    de créer des groupes de manière contiguë. Si on veut créer des
    groupes par ordre alphabétique, on peut utiliser ``--ordered``. On
    peut également fournir une liste de colonnes selon lesquelles
    trier.

    On peut indiquer des contraintes dans la création des groupes avec l'option
    ``--other-groups`` qui spécifie des noms de colonnes de groupes déjà formés
    qu'on va s'efforcer de ne pas reformer. On peut également indiquer des
    affinités dans la création des groupes avec l'option ``--affinity-groups``
    qui spécifie des noms de colonnes de groupes déjà formés qu'on va s'efforcer
    de reformer à nouveau.

    {options}

    Examples
    --------

    - Faire des trinômes à l'intérieur de chaque sous-groupe de TD :

      .. code:: bash

         guv csv_create_groups Projet1 -G TD --group-size 3

    - Faire des trinômes à l'intérieur de chaque sous-groupe de TD en
      s'efforçant de choisir des nouveaux trinômes par rapport à la colonne
      ``Projet1`` :

      .. code:: bash

         guv csv_create_groups Projet2 -G TD --group-size 3 --other-groups Projet1

    - Partager en deux chaque sous-groupe de TD avec des noms de groupes
      de la forme D1i, D1ii, D2i, D2ii... :

      .. code:: bash

         guv csv_create_groups HalfGroup -G TD --proportions .5 .5 --template '{grouping_name}{group_name}' --names i ii

    - Partager l'effectif en deux parties selon l'ordre alphabétique
      avec les noms de groupes ``First`` et ``Second`` :

      .. code:: bash

         guv csv_create_groups Half --proportions .5 .5 --ordered --names First Second --template '{group_name}'

    .. rubric:: Remarques

    Afin qu'il soit correctement chargé par Moodle, le fichier ne
    contient pas d'en-tête spécifiant le nom des colonnes. Pour
    agréger ce fichier de groupes au fichier central, il faut donc
    utiliser l'argument ``kw_read`` comme suit :

    .. code:: python

       DOCS.aggregate(
           "generated/Projet1_groups.csv",
           on="Courriel",
           kw_read={"header": None, "names": ["Courriel", "Groupe P1"]},
       )

    """

    uptodate = False
    target_dir = "generated"
    target_name = "{title}_groups.csv"
    cli_args = (
        argument("title", help="Nom associé à l'ensemble des groupes créés. Repris dans le nom du fichier créé et dans le nom des groupes créés suivant la *template* utilisée."),
        argument(
            "-G",
            "--grouping",
            required=False,
            help="Pré-groupes dans lesquels faire des sous-groupes",
        ),
        argument(
            "-n",
            "--num-groups",
            type=int,
            required=False,
            help="Nombre de groupes à créer (par sous-groupes si spécifié)",
        ),
        argument(
            "-s",
            "--group-size",
            type=int,
            required=False,
            help="Taille des groupes : binômes, trinômes ou plus",
        ),
        argument(
            "-p",
            "--proportions",
            nargs="+",
            type=float,
            required=False,
            help="Liste de proportions pour créer les groupes",
        ),
        argument(
            "-t",
            "--template",
            required=False,
            help="Modèle pour donner des noms aux groupes avec `{title}`, `{grouping_name}` ou `{group_name}`",
        ),
        argument(
            "-l",
            "--names",
            nargs="+",
            required=False,
            help="Liste de mots clés pour construire les noms des groupes",
        ),
        argument(
            "-o",
            "--ordered",
            nargs="*",
            required=False,
            help="Ordonner la liste des étudiants par ordre alphabétique ou par colonnes",
        ),
        argument(
            "-g",
            "--global",
            dest="global_",
            action="store_true",
            help="Ne pas remettre à zéro la suite des noms de groupes entre chaque groupement",
        ),
        argument(
            "-r",
            "--random",
            dest="random",
            action="store_true",
            help="Permuter aléatoirement les noms de groupes",
        ),
        argument(
            "--other-groups",
            nargs="+",
            required=False,
            default=[],
            help="Liste de colonnes de groupes déjà formés qui ne doivent plus être reformés."
        ),
        argument(
            "--affinity-groups",
            nargs="+",
            required=False,
            default=[],
            help="Liste de colonnes de groupes d'affinité."
        ),
        argument(
            "--max-iter",
            type=int,
            default=1000,
            help="Nombre maximum d'essais pour trouver des groupes avec contraintes (par défaut %(default)s)."
        )
    )

    def setup(self):
        super().setup()

        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target = self.build_target()

    def create_name_gen(self, tmpl):
        "Générateur de noms pour les groupes"

        if self.names is None:
            if "@" in tmpl and "#" in tmpl:
                raise Exception(
                    "La template doit contenir soit '@' soit '#' pour générer des noms de groupes différents"
                )
            if "@" in tmpl:
                for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    yield tmpl.replace("@", letter)
            elif "#" in tmpl:
                i = 1
                while True:
                    yield tmpl.replace("#", str(i))
                    i += 1
            else:
                raise Exception(
                    "Pas de # ou de @ dans la template pour générer des noms différents"
                )
        elif len(self.names) == 1:
            path = self.names[0]
            if os.path.exists(path):
                with open(path, "r") as fd:
                    lines = [l.strip() for l in fd.readlines()]
                if self.random:
                    random.shuffle(lines)
                for l in lines:
                    yield pformat(tmpl, group_name=l.strip())
            else:
                raise Exception("Le fichier de noms n'existe pas")
        else:
            names = self.names.copy()
            if self.random:
                random.shuffle(names)
            for n in names:
                yield pformat(tmpl, group_name=n)

    def run(self):
        # Set template used to generate group names
        if self.template is None:
            if self.names is None:
                if self.grouping is None:
                    self.template = "{title}_group_#"
                else:
                    self.template = "{title}_{grouping_name}_group_#"
            else:
                if self.grouping is None:
                    self.template = "{title}_{group_name}"
                else:
                    self.template = "{title}_{grouping_name}_{group_name}"

            logger.info("Pas de template spécifiée. La template par défaut est `%s`", self.template)

        if (self.proportions is not None) + (self.group_size is not None) + (
            self.num_groups is not None
        ) != 1:
            raise self.parser.error(
                "Spécifier un et un seul argument parmi --proportions, --group-size, --num-groups",
            )

        num_placeholders = ("{group_name}" in self.template) + ("@" in self.template) + ("#" in self.template)
        if num_placeholders != 1:
            raise self.parser.error("Spécifier un et un seul remplacement dans la template parmi `@`, `#` et `{group_name}`")

        if "{group_name}" in self.template and self.names is None:
            raise self.parser.error(
                "La template contient '{group_name}' mais --names n'est pas spécifié"
            )

        if "{grouping_name}" in self.template and self.grouping is None:
            raise self.parser.error("La template contient '{grouping_name}' mais aucun groupement n'est spécifié avec l'option --grouping")

        df = XlsStudentDataMerge.read_target(self.xls_merge)

        if self.grouping is not None:
            check_if_present(
                df, self.grouping, file=self.xls_merge, base_dir=self.settings.CWD
            )
            df = df.loc[~df[self.grouping].isnull()]

        if self.other_groups is not None:
            check_if_present(
                df, self.other_groups, file=self.xls_merge, base_dir=self.settings.CWD
            )

        if self.affinity_groups is not None:
            check_if_present(
                df, self.affinity_groups, file=self.xls_merge, base_dir=self.settings.CWD
            )

        # Shuffled or ordered rows according to `ordered`
        if self.ordered is None:
            df = df.sample(frac=1).reset_index(drop=True)
        elif len(self.ordered) == 0:
            df = sort_values(df, ["Nom", "Prénom"])
        else:
            check_if_present(
                df, self.ordered, file=self.xls_merge, base_dir=self.settings.CWD
            )
            df = sort_values(df, self.ordered)

        if self.ordered is not None and (self.affinity_groups or self.other_groups):
            raise self.parser.error("L'option ``ordered`` est incompatible avec les contraintes ``other-groups`` et ``affinity_groups``.")

        # Add title to template
        tmpl = self.template
        tmpl = pformat(tmpl, title=self.title)

        # Set grouping key from grouping cli argument
        key = (lambda x: True) if self.grouping is None else self.grouping

        # Diviser le dataframe en morceaux d'après `key` et faire des
        # groupes dans chaque morceau
        def df_gen():
            name_gen = self.create_name_gen(tmpl)
            for name, df_group in df.groupby(key):
                # Reset name generation for a new group
                if not self.global_:
                    name_gen = self.create_name_gen(tmpl)

                # Make sub-groups for group `name`
                yield self.make_groups(name, df_group, name_gen)

        # Concatenate sub-groups for each grouping
        s_groups = pd.concat(df_gen())

        # Add Courriel column, use index to merge
        df_out = pd.DataFrame({"Login": df["Login"], "group": s_groups})
        df_out = df_out.sort_values(["group", "Login"])

        with Output(self.target) as out:
            df_out.to_csv(out.target, index=False, header=False)

        df_groups = pd.DataFrame({"groupname": df["Login"], 'groupingname': s_groups})
        df_groups = df_groups.sort_values(["groupingname", "groupname"])

        csv_target = os.path.splitext(self.target)[0] + '_secret.csv'
        with Output(csv_target) as out:
            df_groups.to_csv(out.target, index=False)

        if "MOODLE_ID" in self.settings:
            id = str(self.settings.MOODLE_ID)
        else:
            id = "<MOODLE_ID>"

        url = f"https://moodle.utc.fr/local/userenrols/import.php?id={id}"

        logger.info(textwrap.dedent("""\

        Charger les groupes sur Moodle à l'adresse %(url)s en spécifiant :

        - Champ utilisateur: "Nom d'utilisateur"
        - Inscrire dans les groupes : "Oui"
        - Créer les groupes: "Oui" s'il ne sont pas déjà créés

        Ajouter les groupes au fichier `effectifs.xlsx` avec le code suivant dans le fichier `config.py` de l'UV :

        # Créé avec la commande : %(command_line)s
        DOCS.aggregate(
            "%(filename)s",
            on="Login",
            kw_read={"header": None, "names": ["Login", "%(title)s_group"]}
        )
        """ % {
            "url": url,
            "filename": rel_to_dir(self.target, self.settings.UV_DIR),
            "title": self.title,
            "command_line": "guv " + " ".join(map(shlex.quote, sys.argv[1:]))
        }))

    def get_cooc_data(self, df):
        """Return various data to handle group constraints"""

        cooc_repulse_dict = get_coocurrence_dict(df, self.other_groups)
        cooc_repulse = sum(cooc for _, cooc in cooc_repulse_dict.items())
        n_repulse = len(self.other_groups)

        cooc_affinity_dict = get_coocurrence_dict(df, self.affinity_groups)
        cooc_affinity = sum(cooc for _, cooc in cooc_affinity_dict.items())
        n_affinity = len(self.other_groups)

        cooc_final = cooc_repulse - cooc_affinity
        minimum_score = cooc_final.min(axis=None)

        # Final distance matrix: 0 means OK, > 0 means a constraint is violated
        cooc_final = cooc_final - minimum_score
        N = len(df.index)

        return {
            "cooc_cost": cooc_final,
            "min_cost": N * (n_repulse - n_affinity - minimum_score),
            "cooc_repulse_dict": cooc_repulse_dict,
            "cooc_affinity_dict": cooc_affinity_dict
        }

    def search_groups(self, df, cooc_data):
        """Random search of groups that meet constraints"""

        old_cost = np.inf
        niter = 0

        while niter < self.max_iter:
            # New contiguous partition of df.index
            groups = self.make_groups_index(df)

            # Get its coocurrence pandas dataframe
            cooccurence_matrix = get_coocurrence_matrix_from_partition(groups, df.index)

            # Compute cost wrt to constraints
            cost = (cooccurence_matrix * cooc_data["cooc_cost"]).to_numpy().sum()

            # Check if cost is minimal
            if cost == cooc_data["min_cost"]:
                best_groups = groups
                break

            if old_cost > cost:
                old_cost = cost
                best_groups = groups

            # Shuffle to test a different partition
            df = df.sample(frac=1)
            niter += 1

        return best_groups, niter

    def make_groups_aux(self, name, df):
        """Make groups and report"""

        if not self.affinity_groups and not self.other_groups:
            return self.make_groups_index(df)

        cooc_data = self.get_cooc_data(df)
        groups, niter = self.search_groups(df, cooc_data)
        if niter < self.max_iter:
            logger.info(f"Partition optimale pour le groupe `{name}` trouvée en {niter+1} essais.")
        else:
            logger.warning(f"Pas de solution optimale trouvée pour le groupe `{name}` en {self.max_iter} essais, meilleure solution :")

            N = len(df.index)
            best_cm = get_coocurrence_matrix_from_partition(groups, df.index)
            for column, cm in cooc_data["cooc_repulse_dict"].items():
                # Non-zero off-diagonal element of prod signals a common
                # cooccurence.
                prod = cm * best_cm
                if prod.to_numpy(dtype=int).sum() > N:
                    logger.warning(f"- contrainte de non-appartenance par la colonne `{column}` violée {(prod.to_numpy(dtype=int).sum() - N)//2} fois :")

                    # Compute locations as a dataframe of (index, index) where
                    # there is a common cooccurence.
                    df0 = pd.melt(prod.reset_index(), id_vars="index")
                    df0.variable = df0.variable.astype(int)
                    df0 = df0.loc[(df0.value > 0) & (df0["index"] < df0["variable"]), ["index", "variable"]]

                    for index, row in df0.iterrows():
                        i, j = row[["index", "variable"]]
                        stu1 = " ".join(df.loc[i, ["Nom", "Prénom"]])
                        stu2 = " ".join(df.loc[j, ["Nom", "Prénom"]])
                        logger.warning(f"  - {stu1} -- {stu2}")
                else:
                    logger.warning(f"- contrainte de non-appartenance par la colonne `{column}` vérifiée")

            for column, cm in cooc_data["cooc_affinity_dict"].items():
                # Non-zero off-diagonal element of prod signals a common
                # cooccurence.
                prod = (1 - cm) * best_cm
                if prod.to_numpy(dtype=int).sum() > 0:
                    logger.warning(f"- contrainte d'affinité par la colonne `{column}` violée {(prod.to_numpy(dtype=int).sum())//2} fois :")

                    # Compute locations as a dataframe of (index, index) where
                    # there is a common cooccurence.
                    df0 = pd.melt(prod.reset_index(), id_vars="index")
                    df0.variable = df0.variable.astype(int)
                    df0 = df0.loc[(df0.value > 0) & (df0["index"] < df0["variable"]), ["index", "variable"]]

                    for index, row in df0.iterrows():
                        i, j = row[["index", "variable"]]
                        stu1 = " ".join(df.loc[i, ["Nom", "Prénom"]])
                        stu2 = " ".join(df.loc[j, ["Nom", "Prénom"]])
                        logger.warning(f"  - {stu1} -- {stu2}")
                else:
                    logger.warning(f"- contrainte d'affinité par la colonne `{column}` vérifiée")

        return groups

    def make_groups(self, name, df, name_gen):
        """Try to make subgroups in dataframe `df`.

        Returns a Pandas series whose index is the one of `df` and
        value is the group name generated from `name` and `name_gen`.

        """
        groups = self.make_groups_aux(name, df)

        series_list = self.add_names_to_grouping(groups, name, name_gen)

        # Print when groups are in alphabetical order
        if self.ordered is not None and len(self.ordered) == 0:
            for series in series_list:
                first = df.loc[series.index].iloc[0]
                last = df.loc[series.index].iloc[-1]
                print(series.name, ":", first["Nom"], first["Prénom"], "--", last["Nom"], last["Prénom"])

        return pd.concat(series_list)

    def make_groups_index(self, df):
        """Return a partition of the index of dataframe `df`.

        Partition is encoded as a list of lists of elements of the
        index.

        """

        index = df.index

        if self.proportions is not None:
            return make_groups(index, self.proportions)

        elif self.group_size is not None:
            size = self.group_size
            if size > 2:
                # When size is > 2, prefer groups of size size-1 rather
                # than groups of size size+1
                n = len(index)
                n_groups = math.ceil(n / size)
                proportions = np.ones(n_groups)
                return make_groups(index, proportions)
            else:
                # When size is 2, prefer groups of size 3 rather
                # than groups of size 1
                n = len(index)
                n_groups = math.floor(n / size)
                proportions = np.ones(n_groups)
                return make_groups(index, proportions)

        elif self.num_groups is not None:
            proportions = np.ones(self.num_groups)
            return make_groups(index, proportions)

    def add_names_to_grouping(self, groups, name, name_gen):
        """Give names to `groups`"""

        series_list = []
        for group in groups:
            try:
                name_tmpl = next(name_gen)
            except StopIteration as e:
                raise Exception("Les noms de groupes disponibles sont épuisés, utiliser # ou @ dans le modèle ou rajouter des noms dans `--names`.") from e
            group_name = pformat(name_tmpl, grouping_name=name)
            series = pd.Series([group_name]*len(group), index=group, name=group_name)
            series_list.append(series)

        return series_list


class FetchGroupId(TaskBase, CliArgsMixin):
    """Crée un fichier de correspondance entre le nom et l'id des groupes Moodle.

    Pour utiliser certaines fonctionnalités de **guv** (notamment
    :class:`~guv.tasks.moodle.JsonRestriction` et
    :class:`~guv.tasks.moodle.JsonGroup`), il faut connaitre la
    correspondance entre le nom des groupes et leur identifiant dans
    Moodle. Cette tâche permet de télécharger la correspondance en
    indiquant l'identifiant de l'UV/UE sous Moodle. Par exemple, l'id
    de l'url suivante :

        https://moodle.utc.fr/course/view.php?id=1718

    est 1718. La correspondance est téléchargée dans le sous-dossier
    ``document/`` du dossier du semestre. Il suffit ensuite de copier
    son contenu dans le fichier ``config.py`` de l'UV/UE
    correspondante.

    Pour avoir accès à Moodle, les cookies de Firefox sont utilisés.
    Il faut donc préalablement s'être identifié dans Moodle avec
    Firefox.

    {options}

    """

    target_dir = "documents"
    target_name = "group_id_{id}.py"
    url = "https://moodle.utc.fr/group/overview.php?id={id}"
    cli_args = (
        argument(
            "ident_list",
            nargs="+",
            help="Liste des identifiants des UV sur Moodle (id=???? dans l'url)"
        ),
    )

    def setup(self):
        super().setup()
        self.parse_args()

    def cookies(self):
        cj = browser_cookie3.firefox()
        c = {c.name: c.value for c in cj if "moodle.utc.fr" in c.domain}
        if not c:
            raise Exception(
                "Le cookie pour accéder à Moodle n'a pas été trouvé. "
                "Identifiez-vous avec Firefox sur Moodle et recommencez."
            )
        return c

    def groups(self, html_page):
        soup = BeautifulSoup(html_page, "html.parser")

        groups = {}
        for select in soup.find_all("select"):
            if select["name"] in ["group", "grouping"]:
                for option in select.find_all("option"):
                    value = option["value"]
                    if int(value) > 0:
                        groups[option.text] = {
                            "moodle_id": int(value),
                            "moodle_name": option.text
                        }

        return groups

    def run(self):
        cookies = self.cookies()
        for id in self.ident_list:
            req = requests.post(pformat(self.url, id=id), cookies=cookies)
            groups = self.groups(req.text)

            with Output(self.build_target(id=id)) as out:
                with open(out.target, "w") as f:
                    msg = """\

Copier le dictionnaire suivant dans le fichier config.py de l'UV. Tous
les groupes créés sous Moodle sont présents. Il faut s'assurer que les
clés correspondent aux noms des groupes de Cours,TD,TP compris par guv
(de la forme "C", "C1", "D1", "D2", "T1", "T2"...)

                    """

                    f.write(textwrap.indent(msg.strip(), "# "))
                    f.write("\n\n")
                    f.write(yapf.FormatCode("MOODLE_GROUPS = " + pprint.pformat(groups))[0])
