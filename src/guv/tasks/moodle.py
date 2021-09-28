"""
Ce module rassemble les tâches pour interagir avec Moodle : création
de fichiers de groupes officiels de Cours/TD/TP où aléatoires
(binômes, trinômes par groupes) prêt à charger, descriptif de l'UV et
des intervenants sous forme de code HTML à copier-coller dans Moodle,
tableau des créneaux de l'UV sous forme de tableau HTML, création de
fichier Json pour copier-coller des restrictions d'accès en fonction
de l'appartenance à un groupe.
"""

import os
import math
import random
import argparse
import json
import datetime as dt
import pprint
import markdown
import pandas as pd
import numpy as np
import pynliner
import jinja2
import browser_cookie3
import textwrap
import yapf.yapflib.yapf_api as yapf
from bs4 import BeautifulSoup
import requests
import guv

from ..config import logger
from ..utils_config import Output, compute_slots
from ..utils import argument, check_columns, lib_list, sort_values, pformat, make_groups
from ..exceptions import InvalidGroups
from .base import CliArgsMixin, UVTask, TaskBase
from .students import XlsStudentDataMerge
from .utc import CsvAllCourses
from .instructors import (
    XlsInstructors,
    AddInstructors,
    create_insts_list,
    read_xls_details,
    XlsAffectation,
)

from ..scripts.moodle_date import CondDate, CondGroup, CondOr, CondProfil

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"


class CsvGroups(UVTask, CliArgsMixin):
    """Fichiers csv des groupes de Cours/TD/TP/singleton pour Moodle.

    Crée des fichiers csv des groupes de Cours/TD/TP pour chaque UV
    sélectionnée. Avec l'option ``-g``, on peut spécifier d'autres
    groupes à exporter sous Moodle.

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
        df = pd.read_excel(self.xls_merge, engine="openpyxl")

        for ctype, target in zip(self.groups, self.targets):
            if ctype == "singleton":
                dff = df[["Courriel", "Login"]]

                with Output(target) as target:
                    dff.to_csv(target(), index=False, header=False)
            else:
                check_columns(df, ctype, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR)
                dff = df[["Courriel", ctype]]

                with Output(target) as target:
                    dff.to_csv(target(), index=False, header=False)


class CsvGroupsGroupings(UVTask, CliArgsMixin):
    """Fichier csv de groupes et groupements à charger sur Moodle pour les créer.

    Il faut spécifier le nombre de groupes dans chaque groupement avec
    l'argument ``-g`` et le nombre de groupements dans
    ``-G``.

    Le nom des groupements est controlé par un modèle spécifié par
    l'argument ``-F`` (par défault "D##_P1"). Les remplacements
    disponibles sont :

    - ## : remplacé par des nombres
    - @@ : remplacé par des lettres

    Le nom des groupes est controlé par un modèle spécifié par
    l'argument ``-f`` (par défault "D##_P1_@"). Les remplacements
    disponibles sont :

    - # : remplacé par des nombres
    - @ : remplacé par des lettres

    {options}

    """

    target_dir = "generated"
    target_name = "groups_groupings.csv"
    cli_args = (
        argument(
            "-g",
            type=int,
            dest="ngroups",
            required=True,
            help="Nombre de groupes dans chaque groupement",
        ),
        argument(
            "-f",
            dest="ngroupsf",
            default="D##_P1_@",
            help="Format du nom de groupe (defaut: %(default)s)",
        ),
        argument(
            "-G",
            dest="ngroupings",
            type=int,
            required=True,
            help="Nombre de groupements différents",
        ),
        argument(
            "-F",
            dest="ngroupingsf",
            default="D##_P1",
            help="Format du nom de groupement (defaut: %(default)s)",
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

        df_groups = pd.DataFrame({"groupname": groups, 'groupingname': self.groupings})
        with Output(self.target, protected=True) as target:
            df_groups.to_csv(target(), index=False)


class HtmlInst(UVTask):
    """Génère la description des intervenants pour Moodle.

    Crée le fichier ``intervenants.html`` qui peut être utilisé dans
    Moodle pour afficher une description de l'équipe pédagogique avec
    les créneaux assurés.
    """

    target_dir = "generated"
    target_name = "intervenants.html"

    def setup(self):
        super().setup()
        self.insts_details = XlsInstructors.target_from()
        self.insts_uv = XlsAffectation.target_from(**self.info)
        self.target = self.build_target()
        self.file_dep = [self.insts_details, self.insts_uv]

    def run(self):
        df_uv = pd.read_excel(self.insts_uv, engine="openpyxl")
        df_uv = create_insts_list(df_uv)
        df_details = read_xls_details(self.insts_details)

        # Add details from df_details
        df = df_uv.merge(
            df_details, how="left", left_on="Intervenants", right_on="Intervenants"
        )

        dfs = df.sort_values(
            ["Responsable", "SortCourseList", "Statut"], ascending=False
        )
        dfs = dfs.reset_index()

        insts = [
            {
                "inst": row["Intervenants"],
                "libss": row["CourseList"],
                "resp": row["Responsable"],
                "website": row["Website"],
                "email": row["Email"],
            }
            for _, row in dfs.iterrows()
        ]

        def contact(info):
            if not pd.isnull(info["website"]):
                return f'[{info["inst"]}]({info["website"]})'
            elif not pd.isnull(info["email"]):
                return f'[{info["inst"]}](mailto:{info["email"]})'
            else:
                return info["inst"]

        tmpl_dir = os.path.join(guv.__path__[0], "templates")
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
        # env.globals.update(contact=contact)
        template = env.get_template("instructors.html.jinja2")
        md = template.render(insts=insts, contact=contact)
        html = markdown.markdown(md)

        with Output(self.target) as target:
            with open(target(), "w") as fd:
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
            help="Liste ou fichier contenant les noms des colonnes du tableau. Par défaut, les noms de colonnes sont ``D1``, ``D2``,... ou ``T1``, ``T2``,...",
        ),
        argument(
            "--header-row-format",
            default="{beg}--{end}",
            help="Format pour l'en-tête de chaque ligne"
        )
    )

    def setup(self):
        super().setup()
        self.csv_inst_list = AddInstructors.target_from()
        self.file_dep = [self.csv_inst_list]

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

        with Output(target) as target:
            with open(target(), "w") as fd:
                fd.write(output)

    def run(self):
        if len(self.names) == 1:
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

        return dfs.render()

    def get_table(self, courses):
        """Get a Pandas DataFrame from all COURSES"""

        # Select wanted slots
        slots = compute_slots(self.csv_inst_list, self.planning, filter_uvs=[self.uv])
        slots = slots[slots["Activité"].isin(courses)]

        if len(slots) == 0:
            raise Exception("Pas de créneaux pour ", courses)

        def mondays(beg, end):
            while beg <= end:
                nbeg = beg + dt.timedelta(days=7)
                yield (beg, nbeg)
                beg = nbeg

        def merge_slots(df):
            activity = df.iloc[0]["Activité"]

            def to_names(num):
                if self.names is not None:
                    return str(self.names[num - 1])
                else:
                    return str(num)

            if activity in ["Cours", "TD"] or (activity == "TP" and not self.num_AB):
                return ", ".join(df.num.apply(to_names))
            else:
                return ", ".join(df.semaine + df.numAB.apply(to_names))

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
                rows.append(pd.Series())

        # Weeks on rows
        df = pd.concat(rows, axis=1, sort=True).transpose()

        # Reorder columns
        if len(df.columns) > 1:
            cols = sorted(df.columns.tolist(), key=lib_list)
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
    always_make = True

    cli_args = (
        argument(
            "-c",
            "--course",
            default="TP",
            choices=["Cours", "TD", "TP"],
            help="Type de séances considérées. Par défaut, ``Cours``, ``TD``, ``TP`` sont utilisées.",
        ),
        argument(
            "-a", "--num-AB", action="store_true", help="Permet de prendre en compte les semaines A/B. Ainsi, la fin d'une séance est à la fin de la semaine B."
        ),
    )

    def setup(self):
        super().setup()
        self.all_courses = CsvAllCourses.target_from()
        self.file_dep = [self.all_courses]

        self.parse_args()
        AB = "_AB" if self.num_AB else ""
        self.target = self.build_target(AB=AB)

    def run(self):
        df = pd.read_csv(self.all_courses)
        df = df.loc[df["Code enseig."] == self.uv]
        df = df.loc[df["Activité"] == self.course]

        key = "numAB" if self.num_AB else "num"
        gb = df.groupby(key)

        def get_beg_end_date_each(num, df):
            def group_beg_end(row):
                if self.num_AB:
                    group = row["Lib. créneau"] + row["semaine"]
                else:
                    group = row["Lib. créneau"]

                date = row["date"]
                hd = row["Heure début"]
                hf = row["Heure fin"]
                dtd = dt.datetime.strptime(
                    date + "_" + hd, DATE_FORMAT + "_" + TIME_FORMAT
                )
                dtf = dt.datetime.strptime(
                    date + "_" + hf, DATE_FORMAT + "_" + TIME_FORMAT
                )

                return group, dtd, dtf

            gbe = [group_beg_end(row) for index, row in df.iterrows()]
            dt_min = min(b for g, b, e in gbe)
            dt_min3 = dt_min - dt.timedelta(days=3)
            dt_max = max(e for g, b, e in gbe)

            dt_min_monday = dt_min - dt.timedelta(days=dt_min.weekday())
            dt_min_monday = dt.datetime.combine(dt_min_monday, dt.time.min)
            dt_min_midnight = dt.datetime.combine(dt_min, dt.time.min)

            if len(gbe) > 1:
                after_beg_group = [
                    (CondGroup() == g) & (CondDate() >= b) for g, b, e in gbe
                ]
                before_beg_group = [
                    (CondGroup() == g) & (CondDate() < b) for g, b, e in gbe
                ]

            dt_max_friday = dt_max + dt.timedelta(days=6 - dt_max.weekday())
            dt_max_friday = dt.datetime.combine(dt_max_friday, dt.time.max)
            dt_max_midnight = dt.datetime.combine(dt_max, dt.time.max)

            no_group = {
                "visible si: t < min(B)": (CondDate() < dt_min).to_PHP(),
                "visible si: t >= min(B)": (CondDate() >= dt_min).to_PHP(),
                "visible si: t >= min(B)-3days": (CondDate() >= dt_min3).to_PHP(),
                "visible si: t >= max(E)": (CondDate() >= dt_max).to_PHP(),
                "visible si: t < max(E)": (CondDate() < dt_max).to_PHP(),
                "visible si: t >= previous_monday(min(B))": (CondDate() >= dt_min_monday).to_PHP(),
                "visible si: t >= next_friday(max(E))": (CondDate() >= dt_max_friday).to_PHP(),
                "visible si: t >= previous_midnight(min(B))": (CondDate() >= dt_min_midnight).to_PHP(),
                "visible si: t >= next_midnight(max(E))": (CondDate() >= dt_max_midnight).to_PHP(),
            }

            if len(gbe) > 1:
                after_end_group = [
                    (CondGroup() == g) & (CondDate() >= e) for g, b, e in gbe
                ]
                before_end_group = [
                    (CondGroup() == g) & (CondDate() < e) for g, b, e in gbe
                ]

                def window_group_start(g, b, e, p=0, q=0):
                    return (CondGroup() == g) & (CondDate() >= b + dt.timedelta(minutes=p)) & (CondDate() < b + dt.timedelta(minutes=q))

                def window_group(g, b, e, p=0, q=0):
                    return (CondGroup() == g) & (CondDate() >= b + dt.timedelta(minutes=p)) & (CondDate() < e + dt.timedelta(minutes=q))

                def windows(func, gbe, p=0, q=0):
                    return [
                        func(g, b, e, p, q) for g, b, e in gbe
                    ]

                if "MOODLE_GROUPS" not in self.settings or not self.settings.MOODLE_GROUPS:
                    print("WARNING: Plusieurs groupes de Cours/TD/TP et MOODLE_GROUPS non spécifié")
                else:
                    info = dict(groups=self.settings.MOODLE_GROUPS)
                    no_group.update({
                        "visible si: t <= B par groupe": CondOr(before_beg_group).to_PHP(**info),
                        "visible si: t > B par groupe": CondOr(after_beg_group).to_PHP(**info),
                        "visible si: t > E par groupe": CondOr(after_end_group).to_PHP(**info),
                        "visible si: t <= E par groupe": CondOr(before_end_group).to_PHP(**info),
                        "visible si: B <= t < E par groupe": CondOr(windows(window_group, gbe)).to_PHP(**info),
                    })
                    for p, q in ((-3, 5),):
                        no_group[f"visible si: B + {p}min <= t < B + {q}min par groupe"] = CondOr(windows(window_group_start, gbe, p, q)).to_PHP(**info)

                    for p, q in ((0, 15),):
                        no_group[f"visible si: B + {p}min <= t < E + {q}min par groupe"] = CondOr(windows(window_group, gbe, p, q)).to_PHP(**info)

            return "Séance " + str(num), no_group

        moodle_date = dict(get_beg_end_date_each(name, g) for name, g in gb)
        max_len = max(len(s) for s in list(moodle_date.values())[0])
        with Output(self.target, protected=True) as target:
            with open(target(), "w") as fd:
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
    """Fichier json des restrictions d'accès aux ressources sur Moodle par addresse email

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
        df = pd.read_excel(self.xls_merge, engine="openpyxl")

        check_columns(df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR)
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

        with Output(self.target, protected=True) as target:
            with open(target(), "w") as fd:
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


class CsvCreateGroups(UVTask, CliArgsMixin):
    """Création aléatoire de groupes d'étudiants prêt à charger sous Moodle.

    Cette tâche crée un fichier csv d'affectation des étudiants à un
    groupe directement chargeable sous Moodle. Si l'option
    ``--grouping`` est spécifiée les groupes sont créés à l'intérieur
    de chaque sous-groupe (de TP ou TD par exemple).

    Le nombre de groupes créés (au total ou par sous-groupes suivant
    ``--grouping``) est controlé par une les options mutuellement
    exclusives ``--proportions``, ``--group-size`` et
    ``--num-groups``.

    Le nom des groupes est controlé par ``--template``. Les
    remplacements suivants sont disponibles à l'intérieur de
    ``--template`` :

    - ``{title}`` : remplacé par le titre (premier argument)
    - ``{grouping_name}`` : remplacé par le nom du sous-groupe à
      l'intérieur duquel on construit des groupes (si on a spécifié
      ``--grouping``)
    - ``{group_name}`` : nom du groupe en construction (si on a
      spécifié ``--names``)
    - ``#`` : numérotation séquentielle du groupe en construction (si
      `names` n'est pas spécifié)
    - ``@`` : lettre séquentielle du groupe en construction (si
      `names` n'est pas spécifié)

    L'option ``--names`` peut être une liste de noms à utiliser ou un
    fichier contenant une liste de noms ligne par ligne. Il sont pris
    aléatoirement si on spécifie le drapeau `--random`.

    Le drapeau ``--global`` permet de remettre à zéro la génération des
    noms de groupes lorsqu'on change le groupe à l'intérieur duquel on
    construit des sous-groupes (si on a spécifié ``--grouping``).

    Les groupes sont aléatoires par défaut. Pour créer des groupes par
    ordre alphabétique, il faut spécifier le drapeau ``--ordered``.

    {options}

    Examples
    --------

    Faire des trinomes à l'intérieur de chaque sous-groupe de TD :

    .. code:: bash

       guv csv_create_groups Projet1 -G TD --group-size 3


    Partager en deux chaque sous-groupe de TD avec des noms de groupes
    de la former D1i, D1ii, D2i, D2ii... :

    .. code:: bash

       guv csv_create_groups HalfGroup -G TD --proportions .5 .5 --template '{grouping_name}{group_name}' --names i ii

    """

    always_make = True
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
            help="Nombre de groupe à créer (par sous-groupes si spécifié)",
        ),
        argument(
            "-s",
            "--group-size",
            type=int,
            required=False,
            help="Taille des groupes : binomes, trinomes ou plus",
        ),
        argument(
            "-p",
            "--proportions",
            nargs="+",
            type=float,
            required=False,
            help="Nombre de groupes et proportions des ces groupes",
        ),
        argument(
            "-t",
            "--template",
            required=False,
            help="Modèle pour donner des noms aux groupes",
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
            action="store_true",
            help="Ordonner la liste des étudiants par ordre alphabétique",
        ),
        argument(
            "-g",
            "--global",
            dest="global_",
            action="store_true",
            help="Remettre à zéro la suite des noms de sous-groupes",
        ),
        argument(
            "-r",
            "--random",
            dest="random",
            action="store_true",
            help="Permuter aléatoirement les noms de groupes",
        ),
    )

    def setup(self):
        super().setup()

        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target = self.build_target()

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

    def create_name_gen(self, tmpl):
        "Générateur de noms pour les groupes"

        if self.names is None:
            if "@" in tmpl and "#" in tmpl:
                raise Exception("La template doit contenir soit des @ soit des #")
            if "@" in tmpl:
                for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    yield tmpl.replace("@", letter)
            elif "#" in tmpl:
                i = 1
                while True:
                    yield tmpl.replace("#", str(i))
                    i += 1
            else:
                raise Exception("Pas de # ou de @ dans la template pour générer des noms différents")
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
        if (self.proportions is not None) + (self.group_size is not None) + (
            self.num_groups is not None
        ) != 1:
            raise self.parser.error(
                "Spécifier un et un seul argument parmi --proportions, --group-size, --num-groups",
            )

        df = pd.read_excel(self.xls_merge, engine="openpyxl")

        # Shuffled or ordered rows according to `ordered`
        if not self.ordered:
            df = df.sample(frac=1).reset_index(drop=True)
        else:
            df = sort_values(df, ["Nom", "Prénom"])

        if self.grouping is not None:
            check_columns(df, self.grouping, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR)

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
        df_out = pd.DataFrame({"Courriel": df["Courriel"], "group": s_groups})
        df_out = df_out.sort_values(["group", "Courriel"])

        with Output(self.target) as target:
            df_out.to_csv(target(), index=False, header=False)

        df_groups = pd.DataFrame({"groupname": df["Login"], 'groupingname': s_groups})
        df_groups = df_groups.sort_values(["groupingname", "groupname"])

        csv_target = os.path.splitext(self.target)[0] + '_secret.csv'
        with Output(csv_target) as target:
            df_groups.to_csv(target(), index=False)
            logger.warning(str(df_groups.head()))

    def make_groups(self, name, df, name_gen):
        """Try to make subgroups in `df`"""

        for i in range(100000):
            try:
                # Make groups based on proportions, num_groups or
                # group_size.
                groups = self.make_groups_index(df)

                # Check validity (group sizes of 2 and 3 only)
                self.check_valid_groups(df, groups)
            except InvalidGroups:
                df = df.sample(frac=1)
                continue

            logger.warning(f"{i+1} configuration(s) testée(s)")
            return self.add_names_to_grouping(groups, name, name_gen)

        raise Exception(f"Aucune des {i+1} configurations testées n'est valide")

    def make_groups_index(self, df):
        """Use index of `df` to make groups"""

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

    def check_valid_groups(self, df, groups):
        """Check that groups are valid"""

        for idxs in groups:
            if len(idxs) == 2:
                if not self.check_valid_group_2(df, idxs):
                    raise InvalidGroups
            elif len(idxs) == 3:
                if not self.check_valid_group_3(df, idxs):
                    raise InvalidGroups

    def check_valid_group_2(self, df, group):
        idx1, idx2 = group
        etu1, etu2 = df.loc[idx1], df.loc[idx2]

        e = [
            "DIPLOME ETAB ETRANGER SECONDAIRE",
            "DIPLOME ETAB ETRANGER SUPERIEUR",
            "AUTRE DIPLOME UNIVERSITAIRE DE 1ER CYCLE HORS DUT",
        ]

        # 2 étrangers == catastrophe
        if (
            etu1["Dernier diplôme obtenu"] in e
            and etu2["Dernier diplôme obtenu"] in e
        ):
            nom1 = etu1["Nom"] + " " + etu1["Prénom"]
            nom2 = etu2["Nom"] + " " + etu2["Prénom"]
            logger.warning(f"Binôme {nom1} et {nom2} invalide : étrangers")
            return False

        # 2 GB == catastrophe
        if etu1["Branche"] == "GB" and etu2["Branche"] == "GB":
            nom1 = etu1["Nom"] + " " + etu1["Prénom"]
            nom2 = etu2["Nom"] + " " + etu2["Prénom"]
            logger.warning(f"Binôme {nom1} et {nom2} invalide : GB")
            return False

        # Binomes précédents
        if other_groups is not None:
            for gp in other_groups:
                if etu1[gp] == etu2[gp]:
                    return False

        return True

    def check_valid_group_3(self, df, group):
        idx1, idx2, idx3 = group

        a = self.check_valid_group_2(df, [idx1, idx2])
        b = self.check_valid_group_2(df, [idx1, idx3])
        c = self.check_valid_group_2(df, [idx2, idx3])

        if other_groups is not None:
            etu1 = df.loc[idx1]
            etu2 = df.loc[idx2]
            etu3 = df.loc[idx3]

            for gp in other_groups:
                if len(set([etu1[gp], etu2[gp], etu3[gp]])) != 3:
                    return False

        return a or b or c

    def add_names_to_grouping(self, groups, name, name_gen):
        """Give names to `groups`"""

        def name_gen0():
            for n in name_gen:
                yield pformat(n, grouping_name=name)

        series_list = [
            pd.Series([group_name]*len(group), index=group)
            for group_name, group in zip(name_gen0(), groups)
        ]

        return pd.concat(series_list)


class FetchGroupId(CliArgsMixin, TaskBase):
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

            with Output(self.build_target(id=id)) as target:
                with open(target(), "w") as f:
                    msg = """\

Copier le dictionnaire suivant dans le fichier config.py de l'UV. Tous
les groupes créés sous Moodle sont présents. Il faut s'assurer que les
clés correspondent aux noms des groupes de Cours,TD,TP compris par guv
(de la forme "C", "C1", "D1", "D2", "T1", "T2"...)

                    """

                    f.write(textwrap.indent(msg.strip(), "# "))
                    f.write("\n\n")
                    f.write(yapf.FormatCode("MOODLE_GROUPS = " + pprint.pformat(groups))[0])
