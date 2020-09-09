"""
Fichier qui regroupe des tâches pour interagir avec Moodle : création
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
from datetime import timedelta, datetime, time
import pandas as pd
import numpy as np
import pynliner
import jinja2
import markdown

from .utils_config import Output, documents, generated, compute_slots
from .utils import argument, check_columns, lib_list
from .tasks import CliArgsMixin, UVTask
from .utils import pformat, make_groups
from .dodo_students import XlsStudentDataMerge
from .dodo_utc import CsvAllCourses
from .dodo_instructors import (
    AddInstructors,
    create_insts_list,
    read_xls_details,
    XlsAffectation,
)

from .scripts.moodle_date import CondDate, CondGroup, CondOr, CondProfil

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"


class HtmlInst(UVTask):
    "Génère la description des intervenants pour Moodle"

    target = "intervenants.html"

    def __init__(self, uv, planning, info):
        super().__init__(uv, planning, info)
        self.insts_details = documents("intervenants.xlsx")
        self.insts_uv = documents(XlsAffectation.target, **info)
        self.target = generated(HtmlInst.target, **info)

    def run(self):
        df_uv = pd.read_excel(self.insts_uv)
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

        jinja_dir = os.path.join(os.path.dirname(__file__), "templates")
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(jinja_dir))
        # env.globals.update(contact=contact)
        template = env.get_template("instructors.html.jinja2")
        md = template.render(insts=insts, contact=contact)
        html = markdown.markdown(md)

        with Output(self.target) as target:
            with open(target(), "w") as fd:
                fd.write(html)


class HtmlTable(UVTask, CliArgsMixin):
    """Table HTML des TD/TP"""

    cli_args = (
        argument(
            "-c",
            "--courses",
            nargs="*",
            default=["Cours", "TD", "TP"],
            help="Liste des cours à faire figurer dans le tableau",
        ),
        argument(
            "-g",
            "--grouped",
            action="store_true",
            help="Grouper les cours dans le même tableau ou faire des fichiers distincts",
        ),
        argument(
            "-a",
            "--no-AB",
            action="store_true",
            help="Faire apparaitre les semaines A/B",
        ),
        argument(
            "-n",
            "--names",
            nargs="*",
            help="Liste ou fichier contenant les noms des lignes du tableau",
        ),
    )

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)

        self.csv_inst_list = generated(AddInstructors.target)
        self.file_dep = [self.csv_inst_list]

        if self.grouped:
            name = "_".join(self.courses) + "_grouped"
            if self.no_AB:
                name += "_no_AB"
            self.target = generated(f"{name}_table.html", **self.info)
        else:
            self.targets = [
                generated(f"{course}_table.html", **self.info)
                for course in self.courses
            ]

    def write_html_table(self, target, html):
        # Inline style for Moodle
        output = pynliner.fromString(html)

        with Output(target) as target:
            with open(target(), "w") as fd:
                fd.write(output)

    def run(self):
        # Set names

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
                nbeg = beg + timedelta(days=7)
                yield (beg, nbeg)
                beg = nbeg

        def merge_slots(df):
            activity = df.iloc[0]["Activité"]

            def to_names(num):
                if self.names is not None:
                    return str(self.names[num - 1])
                else:
                    return str(num)

            if activity in ["Cours", "TD"] or (activity == "TP" and self.no_AB):
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
                    mon.strftime("%d/%m"), (nmon - timedelta(days=1)).strftime("%d/%m")
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
    """Ficher json des restrictions d'accès aux ressources sur Moodle
basées sur le début/fin des séances."""

    cli_args = (
        argument(
            "-c",
            "--course",
            default="TP",
            choices=["Cours", "TD", "TP"],
            help="Type de séances considérées",
        ),
        argument(
            "-a", "--AB", action="store_true", help="Prise en compte des semaines A/B"
        ),
    )

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        AB = "_AB" if self.AB else ""
        target_fn = f"moodle_restrictions_{self.course}{AB}.json"
        self.target = generated(target_fn, **self.info)
        self.all_courses = generated(CsvAllCourses.target)
        self.file_dep = [self.all_courses]

    def run(self):
        df = pd.read_csv(self.all_courses)
        df = df.loc[df["Code enseig."] == self.uv]
        df = df.loc[df["Activité"] == self.course]

        key = "numAB" if self.AB else "num"
        gb = df.groupby(key)

        def get_beg_end_date_each(num, df):
            def group_beg_end(row):
                if self.AB:
                    group = row["Lib. créneau"] + row["semaine"]
                else:
                    group = row["Lib. créneau"]

                date = row["date"]
                hd = row["Heure début"]
                hf = row["Heure fin"]
                dtd = datetime.strptime(
                    date + "_" + hd, DATE_FORMAT + "_" + TIME_FORMAT
                )
                dtf = datetime.strptime(
                    date + "_" + hf, DATE_FORMAT + "_" + TIME_FORMAT
                )

                return group, dtd, dtf

            gbe = [group_beg_end(row) for index, row in df.iterrows()]
            dt_min = min(b for g, b, e in gbe)
            dt_max = max(e for g, b, e in gbe)

            dt_min_monday = dt_min - timedelta(days=dt_min.weekday())
            dt_min_monday = datetime.combine(dt_min_monday, time.min)
            dt_min_midnight = datetime.combine(dt_min, time.min)
            after_beg_group = [
                (CondGroup() == g) & (CondDate() >= b) for g, b, e in gbe
            ]
            before_beg_group = [
                (CondGroup() == g) & (CondDate() < b) for g, b, e in gbe
            ]

            dt_max_friday = dt_max + timedelta(days=6 - dt_max.weekday())
            dt_max_friday = datetime.combine(dt_max_friday, time.max)
            dt_max_midnight = datetime.combine(dt_max, time.max)
            after_end_group = [
                (CondGroup() == g) & (CondDate() >= e) for g, b, e in gbe
            ]
            before_end_group = [
                (CondGroup() == g) & (CondDate() < e) for g, b, e in gbe
            ]

            window_group = [
                (CondGroup() == g) & (CondDate() >= b) & (CondDate() < e)
                for g, b, e in gbe
            ]

            info = dict(group_id=self.settings.GROUP_ID)
            return (
                "Séance " + str(num),
                {
                    "visible si: t < min(B)": (CondDate() < dt_min).to_PHP(**info),
                    "visible si: t >= min(B)": (CondDate() >= dt_min).to_PHP(**info),
                    "visible si: t >= max(E)": (CondDate() >= dt_max).to_PHP(**info),
                    "visible si: t < max(E)": (CondDate() < dt_max).to_PHP(**info),
                    "visible si: t >= previous_monday(min(B))": (CondDate() >= dt_min_monday).to_PHP(**info),
                    "visible si: t >= next_friday(max(E))": (CondDate() >= dt_max_friday).to_PHP(**info),
                    "visible si: t >= previous_midnight(min(B))": (CondDate() >= dt_min_midnight).to_PHP(**info),
                    "visible si: t >= next_midnight(max(E))": (CondDate() >= dt_max_midnight).to_PHP(**info),
                    "visible si: t <= B par groupe": CondOr(before_beg_group).to_PHP(**info),
                    "visible si: t > B par groupe": CondOr(after_beg_group).to_PHP(**info),
                    "visible si: t > E par groupe": CondOr(after_end_group).to_PHP(**info),
                    "visible si: t <= E par groupe": CondOr(before_end_group).to_PHP(**info),
                    "visible si: B <= t < E par groupe": CondOr(window_group).to_PHP(**info),
                },
            )

        moodle_date = dict(get_beg_end_date_each(name, g) for name, g in gb)

        max_len = len("visible si: t >= previous_midnight(min(B))")
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
    """Fichier json des restrictions d'accès aux ressources sur Moodle.

Les restrictions se font par adresse email.
"""

    cli_args = (
        argument(
            "-g",
            "--group",
            required=True,
            help="Nom de la colonne réalisant un groupement",
        ),
    )

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)

        self.xls_merge = generated(XlsStudentDataMerge.target, **info)
        self.target = generated(f"{self.group}_group_moodle.json", **info)
        self.file_dep = [self.xls_merge]

    def run(self):
        df = pd.read_excel(self.xls_merge)

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
    "Création de groupes prêt à charger sous Moodle"

    always_make = True

    cli_args = (
        argument("title", help="Nom associé à l'ensemble des groupes créés"),
        argument(
            "-G",
            "--grouping",
            required=False,
            help="Pré-groupes dans lesquels faire des sous-groupes",
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
        argument(
            "-t",
            "--template",
            required=False,
            help="Modèle pour donner des noms aux groupes",
        ),
        argument(
            "-l",
            "--names",
            required=False,
            help="Liste de mots clés pour construire les noms des groupes",
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
            help="Taille des groupes, binomes, trinomes ou plus",
        ),
        argument(
            "-p",
            "--proportions",
            nargs="+",
            type=int,
            required=False,
            help="Nombre de groupes et proportions des ces groupes",
        ),
    )

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        # Set dependencies
        self.xls_merge = generated(XlsStudentDataMerge.target, **self.info)
        self.file_dep = [self.xls_merge]

        # Set targets
        self.targets = [generated(f"{self.title}_groups.csv", **self.info)]

        if (
            self.proportions is None
            and self.group_size is None
            and self.num_groups is None
        ):
            raise argparse.ArgumentError(
                None,
                "Spécifier un argument parmi --proportions, --group-size, --num-groups",
            )

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

    def run(self):
        df = pd.read_excel(self.xls_merge)

        # Shuffle rows
        df = df.sample(frac=1).reset_index(drop=True)

        if self.grouping is not None:
            check_columns(df, self.grouping, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR)

        # Ajouter le titre à la template
        tmpl = self.template
        tmpl = pformat(tmpl, title=self.title)

        # Générateur de noms pour les groupes basé sur l'argument
        # `names`
        def create_name_gen():
            "Générateur de noms pour les groupes"

            if self.names is None:
                if "@" in tmpl:
                    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                        yield tmpl.replace("@", letter)
                elif "#" in tmpl:
                    i = 1
                    while True:
                        yield tmpl.replace("#", str(i))
                        i += 1
                else:
                    raise Exception("Pas de # ou de @ pour générer des noms")
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
                for n in self.names:
                    yield pformat(tmpl, group_name=n)

        key = (lambda x: True) if self.grouping is None else self.grouping

        # Diviser le dataframe en morceaux d'après `key` et faire des
        # groupes dans chaque morceau
        def df_gen():
            name_gen = create_name_gen()
            for name, df_group in df.groupby(key):
                if not self.global_:
                    name_gen = create_name_gen()
                yield self.make_groups(name, df_group, name_gen)

        s_groups = pd.concat(df_gen())
        df_out = pd.concat((df["Courriel"], s_groups), axis=1)

        with Output(self.targets[0]) as target:
            df_out.to_csv(target(), index=False, header=False)

        df_groups = pd.DataFrame({"groupname": df["Login"], 'groupingname': s_groups})
        csv_target = os.path.splitext(self.targets[0])[0] + '_secret.csv'
        with Output(csv_target) as target:
            df_groups.to_csv(target(), index=False)

    def make_groups(self, name, df, name_gen):
        """Faire des groupes avec le dataframe `df` nommé `name`"""

        n = df.shape[0]

        def name_gen0():
            for n in name_gen:
                yield pformat(n, grouping_name=name)

        if self.proportions is not None:
            return pd.Series(
                make_groups(n, self.proportions, name_gen0()), index=df.index
            )

        elif self.group_size is not None:
            size = self.group_size
            if size > 3:
                n_groups = math.ceil(n / size)
                proportions = np.ones(n_groups)
                return pd.Series(
                    make_groups(n, proportions, name_gen0()), index=df.index
                )

        elif self.num_groups is not None:
            proportions = np.ones(self.num_groups)
            return pd.Series(make_groups(n, proportions, name_gen0()), index=df.index)
