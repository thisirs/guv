import os
import math
import random
import numpy as np
import pandas as pd
from datetime import timedelta, datetime, time
import json
import pynliner

from doit.exceptions import TaskFailed

from .config import settings
from .utils import (
    Output,
    generated,
    selected_uv,
    compute_slots,
    actionfailed_on_exception,
    taskfailed_on_exception,
    parse_args,
    argument,
    check_columns,
    get_unique_uv,
    DATE_FORMAT,
    TIME_FORMAT,
    lib_list,
)
from .tasks import CliArgsMixin, SingleUVTask
from .utils_noconfig import pformat, make_groups
from .dodo_students import task_xls_student_data_merge
from .dodo_utc import task_csv_all_courses

from .scripts.moodle_date import CondDate, CondGroup, CondOr, CondProfil


@actionfailed_on_exception
def task_html_table():
    """Table HTML des TD/TP"""

    def html_table(planning, csv_inst_list, uv, courses, target, no_AB, names):
        # Select wanted slots
        slots = compute_slots(csv_inst_list, planning, filter_uvs=[uv])
        slots = slots[slots["Activité"].isin(courses)]

        # Fail if no slot
        if len(slots) == 0:
            if len(courses) > 1:
                return TaskFailed(
                    f"Pas de créneau pour le planning `{planning}', l'uv `{uv}' et les cours `{', '.join(courses)}'"
                )
            else:
                print(f"Pas de créneaux pour l'activité {courses[0]}")
                return

        def mondays(beg, end):
            while beg <= end:
                nbeg = beg + timedelta(days=7)
                yield (beg, nbeg)
                beg = nbeg

        def merge_slots(df):
            activity = df.iloc[0]["Activité"]

            def to_names(num):
                if names is not None:
                    return str(names[num - 1])
                else:
                    return str(num)

            if activity == "Cours":
                return ", ".join(df.num.apply(to_names))
            elif activity == "TD":
                return ", ".join(df.num.apply(to_names))
            elif activity == "TP":
                if no_AB:
                    return ", ".join(df.num.apply(to_names))
                else:
                    return ", ".join(df.semaine + df.numAB.apply(to_names))
            else:
                raise Exception("Unrecognized activity", activity)

        # Iterate on each week of semester
        rows = []
        weeks = []
        for (mon, nmon) in mondays(
            settings.PLANNINGS[planning]["PL_BEG"],
            settings.PLANNINGS[planning]["PL_END"],
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

        html = dfs.render()

        # Inline style for Moodle
        output = pynliner.fromString(html)

        with Output(target) as target:
            with open(target(), "w") as fd:
                fd.write(output)

    args = parse_args(
        task_html_table,
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

    from .dodo_instructors import task_add_instructors

    dep = generated(task_add_instructors.target)
    uvs = list(selected_uv())

    if args.names is not None:
        if len(uvs) != 1:
            raise Exception

        if len(args.names) == 1:
            if os.path.exists(args.names[0]):
                with open(args.names[0], "r") as fd:
                    names = fd.readlines()
            else:
                raise Exception
        else:
            names = args.names
    else:
        names = None

    for planning, uv, info in uvs:
        if args.grouped:
            name = "_".join(args.courses)
            if args.grouped:
                name += "_grouped"
            if args.no_AB:
                name += "_no_AB"
            target = generated(f"{name}_table.html", **info)
            yield {
                "name": f"{planning}_{uv}_{name}",
                "file_dep": [dep],
                "actions": [
                    (
                        html_table,
                        [planning, dep, uv, args.courses, target, args.no_AB, names],
                    )
                ],
                "targets": [target],
            }
        else:
            for course in args.courses:
                target = generated(f"{course}_table.html", **info)
                yield {
                    "name": f"{planning}_{uv}_{course}",
                    "file_dep": [dep],
                    "actions": [
                        (
                            html_table,
                            [planning, dep, uv, [course], target, args.no_AB, names],
                        )
                    ],
                    "targets": [target],
                    "verbosity": 2,
                }


@actionfailed_on_exception
def task_json_restriction():
    """Ficher json des restrictions d'accès aux ressources sur Moodle
basées sur le début/fin des séances."""

    def restriction_list(csv, uv, course, AB, target):
        df = pd.read_csv(csv)
        df = df.loc[df["Code enseig."] == uv]
        df = df.loc[df["Activité"] == course]
        gb = df.groupby(AB)

        def get_beg_end_date_each(num, df):
            def group_beg_end(row):
                if AB == "numAB":
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

            info = dict(group_id=settings.GROUP_ID)
            return (
                "Séance " + str(num),
                {
                    "début minuit": (CondDate() >= dt_min_midnight).to_PHP(**info),
                    "début": (CondDate() >= dt_min).to_PHP(**info),
                    "début lundi": (CondDate() >= dt_min_monday).to_PHP(**info),
                    "début par groupe": CondOr(after_beg_group).to_PHP(**info),
                    "fin minuit": (CondDate() >= dt_max_midnight).to_PHP(**info),
                    "fin": (CondDate() >= dt_max).to_PHP(**info),
                    "fin vendredi": (CondDate() >= dt_max_friday).to_PHP(**info),
                    "fin par groupe": CondOr(after_end_group).to_PHP(**info),
                    "créneaux par groupe": CondOr(window_group).to_PHP(**info),
                },
            )

        moodle_date = dict(get_beg_end_date_each(name, g) for name, g in gb)

        with Output(target, protected=True) as target:
            with open(target(), "w") as fd:
                s = (
                    "{\n"
                    + ",\n".join(
                        (
                            f'  "{slot}": {"{"}\n'
                            + ",\n".join(
                                (
                                    f'    "{name}": {" " * (16 - len(name))}'
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

    args = parse_args(
        task_json_restriction,
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

    planning, uv, info = get_unique_uv()
    AB = "numAB" if args.AB else "num"
    course = args.course
    if AB == "numAB":
        target_fn = f"moodle_restrictions_{course}_AB.json"
    else:
        target_fn = f"moodle_restrictions_{course}.json"

    target = generated(target_fn, **info)
    dep = generated(task_csv_all_courses.target)

    return {
        "actions": [(restriction_list, [dep, uv, course, AB, target])],
        "file_dep": [dep],
        "targets": [target],
        "uptodate": [False],
    }


@actionfailed_on_exception
def task_json_group():
    """Fichier json des restrictions d'accès aux ressources sur Moodle."""

    @taskfailed_on_exception
    def json_group(target, xls_merge, colname):
        df = pd.read_excel(xls_merge)

        check_columns(df, colname, file=task_xls_student_data_merge.target)
        dff = df[["Adresse de courriel", colname]]

        json_dict = {
            group_name: CondOr(
                [
                    CondProfil("email") == row["Adresse de courriel"]
                    for index, row in group.iterrows()
                ]
            ).to_PHP()
            for group_name, group in dff.groupby(colname)
        }

        with Output(target, protected=True) as target:
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

    args = parse_args(
        task_json_group,
        argument(
            "-g",
            "--group",
            required=True,
            help="Nom de la colonne réalisant un groupement",
        ),
    )

    for planning, uv, info in selected_uv():
        deps = [generated(task_xls_student_data_merge.target, **info)]
        target = generated(f"{args.group}_group_moodle.json", **info)

        yield {
            "name": f"{planning}_{uv}_{args.group}",
            "actions": [(json_group, [target, deps[0], args.group])],
            "file_dep": deps,
            "targets": [target],
            "verbosity": 2,
        }


class CsvCreateGroups(CliArgsMixin, SingleUVTask):
    "Création de groupes prêt à charger sous Moodle"

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
            help="Utilisation des noms",
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

    def __init__(self):
        super().__init__()
        # Set dependencies
        self.xls_merge = generated(task_xls_student_data_merge.target, **self.info)
        self.deps = [self.xls_merge]

        # Set targets
        self.targets = [generated(f"{self.title}_groups.csv", **self.info)]

        if (
            self.proportions is None
            and self.group_size is None
            and self.num_groups is None
        ):
            raise Exception("Spécifier au moins prop, num ou size")

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
            check_columns(df, self.grouping, file=self.xls_merge)

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
        df = pd.concat((df["Courriel"], s_groups), axis=1)

        with Output(self.targets[0]) as target:
            df.to_csv(target(), index=False, header=False)

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
