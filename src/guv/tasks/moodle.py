import json
import math
import os
from pathlib import Path
import random
import shlex
import sys

import numpy as np
import pandas as pd

from ..exceptions import GuvUserError
from ..logger import logger
from ..scripts.moodle_date import CondOr, CondProfil
from ..translations import _, TaskDocstring, _file
from ..utils import (
    argument,
    generate_groupby,
    make_groups,
    normalize_string,
    pformat,
    sort_values,
)
from ..utils_config import Output, rel_to_dir
from .base import CliArgsMixin, UVTask
from .evolutionary_algorithm import evolutionary_algorithm
from .internal import XlsStudentData


__all__ = ["CsvCreateGroups", "CsvGroups", "CsvGroupsGroupings"]


DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"


class CsvGroups(UVTask, CliArgsMixin):
    __doc__ = TaskDocstring()

    uptodate = False
    target_dir = "generated"
    target_name = "{ctype}_group_moodle.csv"

    cli_args = (
        argument(
            "-g",
            "--groups",
            metavar="COL,[COL,...]",
            type=lambda t: [s.strip() for s in t.split(",")],
            default=[_("Lecture"), _("Tutorial"), _("Practical work")],
            help=_("List of groupings to consider via a column name. By default, the groupings ``Lecture``, ``Tutorial`` and ``Practical work`` are used."),
        ),
        argument(
            "-l",
            "--long",
            action="store_true",
            help=_("Use the names of Lecture/Tutorial/Practical work groups in long format, i.e., \"TP1\" and "
                   "\"TD1\" instead of \"T1\" and \"D1\"")
        ),
        argument(
            "-s",
            "--single",
            action="store_true",
            help=_("Create a single file")
        )
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentData.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.parse_args()
        if self.single:
            ctype = "_".join(normalize_string(s, type="file") for s in self.groups)
            self.targets = [self.build_target(ctype=ctype)]
        else:
            self.targets = [
                self.build_target(ctype=normalize_string(ctype, type="file"))
                for ctype in self.groups
            ]

    def build_dataframes(self, df):
        dfs = []
        for column_name in self.groups:
            if self.check_if_present(
                df,
                column_name,
                file=self.xls_merge,
                base_dir=self.settings.SEMESTER_DIR,
                errors="warning",
            ):
                null = df[column_name].isnull()
                if null.any():
                    for index, row in df.loc[null].iterrows():
                        stu = row[self.settings.LASTNAME_COLUMN] + " " + row[self.settings.NAME]
                        logger.warning(_("Value not defined in the column `{colname}` for the student {stu}").format(colname=column_name, stu=stu))

                dff = df.loc[~null][["Login", column_name]]

                if column_name in ["TP", "TD"] and self.long:
                    new_col = (
                        dff[column_name]
                        .str.replace("D([0-9]+)", r"TD\1", regex=True)
                        .replace("T([0-9]+)", r"TP\1", regex=True)
                    )

                    dff = dff.assign(**{column_name: new_col})

                # Rename columns to be able to (eventually) concatenate
                dff.columns = range(2)

                dfs.append(dff)

        return dfs

    def run(self):
        df = XlsStudentData.read_target(self.xls_merge)

        columns = [self.settings[e] for e in ["NAME_COLUMN", "LASTNAME_COLUMN", "LOGIN_COLUMN"]]
        self.check_if_present(df, columns)

        dfs = self.build_dataframes(df)

        if self.single:
            df_final = pd.concat(dfs)
            target = self.targets[0]
            with Output(target) as out:
                df_final.to_csv(out.target, index=False, header=False)
        else:
            for df, target in zip(dfs, self.targets):
                with Output(target) as out:
                    df.to_csv(out.target, index=False, header=False)

        if "MOODLE_ID" in self.settings:
            id = str(self.settings.MOODLE_ID)
        else:
            id = "<MOODLE_ID>"

        if "MOODLE_URL" in self.settings:
            url = str(self.settings.MOODLE_URL)
        else:
            url = "<MOODLE_URL>"

        url = f"{url}/local/userenrols/import.php?id={id}"
        logger.info(_file("CsvGroups_message").format(url=url))


class CsvGroupsGroupings(UVTask, CliArgsMixin):
    __doc__ = TaskDocstring()

    target_dir = "generated"
    target_name = "groups_groupings.csv"
    cli_args = (
        argument(
            "-g",
            type=int,
            metavar="N_GROUPS",
            dest="ngroups",
            required=True,
            help=_("Number of groups in each grouping"),
        ),
        argument(
            "-f",
            dest="ngroupsf",
            metavar="FORMAT",
            default="D##_P1_@",
            help=_("Format of the group name (default: %(default)s)"),
        ),
        argument(
            "-G",
            dest="ngroupings",
            metavar="N_GROUPINGS",
            type=int,
            required=True,
            help=_("Number of different groupings"),
        ),
        argument(
            "-F",
            dest="ngroupingsf",
            metavar="FORMAT",
            default="D##_P1",
            help=_("Format of the grouping name (default: %(default)s)"),
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


class JsonGroup(UVTask, CliArgsMixin):
    __doc__ = TaskDocstring()

    target_dir = "generated"
    target_name = "{group}_group_moodle.json"
    cli_args = (
        argument(
            "-g",
            "--group",
            required=True,
            help=_("Name of the column performing a grouping"),
        ),
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentData.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target = self.build_target(group=normalize_string(self.group, type="file"))

    def run(self):
        df = XlsStudentData.read_target(self.xls_merge)

        self.check_if_present(
            df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
        )
        dff = df[[self.settings.MOODLE_EMAIL_COLUMN, self.group]]

        # Dictionary of group in GROUP and corresponding Cond
        # object for that group.
        json_dict = {
            group_name: CondOr(
                [
                    CondProfil("email") == row[self.settings.MOODLE_EMAIL_COLUMN]
                    for index, row in group.iterrows()
                ]
            ).to_json()
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


def get_coocurrence_matrix_from_partition(series, nan_policy="same"):
    """Return co-occurrence matrix of vector."""

    if nan_policy == "same":
        s_filled = series.fillna("unique_value_1")
    elif nan_policy == "different":
        unique_values = pd.Series([f"unique_value_{i}" for i in range(len(series))], index=series.index)
        s_filled = series.fillna(unique_values)
    else:
        raise ValueError("Wrong nan_policy")

    arr = s_filled.to_numpy()
    return get_coocurrence_matrix_from_array(arr)


def get_coocurrence_matrix_from_array(arr):
    return (arr[:, None] == arr[None, :]).astype(int)


def get_coocurrence_dict(df, columns, nan_policy="same"):
    """Return a dictionary mapping column with their co-occurrence matrix."""
    cooc_dict = {}
    for column in columns:
        series = df[column]
        cooc = get_coocurrence_matrix_from_partition(series, nan_policy=nan_policy)
        if column in cooc_dict:
            cooc_dict[column] = cooc_dict[column] + cooc
        else:
            cooc_dict[column] = cooc
    return cooc_dict


class CsvCreateGroups(UVTask, CliArgsMixin):
    __doc__ = TaskDocstring()

    uptodate = False
    target_dir = "generated"
    target_name = "{title}_groups.csv"
    cli_args = (
        argument("title", help=_("Name associated with the set of created groups. Included in the name of the created file and in the name of the created groups following the used *template*.")),
        argument(
            "-G",
            "--grouping",
            required=False,
            help=_("Pre-groups in which to make sub-groups"),
        ),
        argument(
            "-n",
            "--num-groups",
            type=int,
            required=False,
            help=_("Number of groups to create (per sub-groups if specified)"),
        ),
        argument(
            "-s",
            "--group-size",
            type=int,
            required=False,
            help=_("Group size: pairs, trios or more"),
        ),
        argument(
            "-p",
            "--proportions",
            nargs="+",
            type=float,
            required=False,
            help=_("List of proportions to create the groups"),
        ),
        argument(
            "-t",
            "--template",
            dest="_template",
            required=False,
            help=_("Template to give names to the groups with `{title}`, `{grouping_name}` or `{group_name}`"),
        ),
        argument(
            "-l",
            "--names",
            nargs="+",
            required=False,
            help=_("List of keywords to build the group names"),
        ),
        argument(
            "-o",
            "--ordered",
            nargs="?",
            default=None,
            const=[],
            metavar="COL,...",
            type=lambda t: [s.strip() for s in t.split(",")],
            required=False,
            help=_("Order the list of students alphabetically or by columns"),
        ),
        argument(
            "-g",
            "--global",
            dest="global_",
            action="store_true",
            help=_("Do not reset the sequence of group names between each grouping"),
        ),
        argument(
            "-r",
            "--random",
            dest="random",
            action="store_true",
            help=_("Randomly permute the group names"),
        ),
        argument(
            "--other-groups",
            required=False,
            metavar="COL,[COL,...]",
            default=[],
            type=lambda t: [s.strip() for s in t.split(",")],
            help=_("List of columns of already formed groups that should not be reformed.")
        ),
        argument(
            "--affinity-groups",
            required=False,
            metavar="COL,[COL,...]",
            default=[],
            type=lambda t: [s.strip() for s in t.split(",")],
            help=_("List of columns of affinity groups.")
        ),
        argument(
            "--max-iter",
            type=int,
            default=1000,
            help=_("Maximum number of attempts to find groups with constraints (default %(default)s).")
        )
    )

    def setup(self):
        super().setup()

        self.xls_merge = XlsStudentData.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target = self.build_target(title=normalize_string(self.title, type="file"))

    def create_name_gen(self, tmpl):
        "Générateur de noms pour les groupes"

        if self.names is None:
            if "@" in tmpl and "#" in tmpl:
                raise self.parser.error(
                    _("The template must contain either '@' or '#' to generate different group names")
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
                raise self.parser.error(
                    _("No # or @ in the template to generate different names")
                )
        elif len(self.names) == 1:
            path = self.names[0]
            if Path(path).exists():
                with open(path, "r") as fd:
                    lines = [l.strip() for l in fd.readlines()]
                if self.random:
                    random.shuffle(lines)
                for l in lines:
                    yield pformat(tmpl, group_name=l.strip())
            else:
                raise FileNotFoundError(_("The name file `{names}` does not exist").format(names=self.names[0]))
        else:
            names = self.names.copy()
            if self.random:
                random.shuffle(names)
            for n in names:
                yield pformat(tmpl, group_name=n)

    @property
    def template(self):
        # Set template used to generate group names
        if self._template is None:
            if self.names is None:
                if self.grouping is None:
                    self._template = "{title}_group_#"
                else:
                    self._template = "{title}_{grouping_name}_group_#"
            else:
                if self.grouping is None:
                    self._template = "{title}_{group_name}"
                else:
                    self._template = "{title}_{grouping_name}_{group_name}"

            logger.info(_("No template specified. The default template is `%s`"), self._template)

        return self._template

    def run(self):
        if (self.proportions is not None) + (self.group_size is not None) + (
            self.num_groups is not None
        ) != 1:
            raise self.parser.error(
                _("Specify one and only one argument among --proportions, --group-size, --num-groups"),
            )

        num_placeholders = ("{group_name}" in self.template) + ("@" in self.template) + ("#" in self.template)
        if num_placeholders != 1:
            raise self.parser.error(_("Specify one and only one replacement in the template among `@`, `#` and `{group_name}`"))

        if "{group_name}" in self.template and self.names is None:
            raise self.parser.error(
                _("The template contains '{group_name}' but --names is not specified")
            )

        if "{grouping_name}" in self.template and self.grouping is None:
            raise self.parser.error(_("The template contains '{grouping_name}' but no grouping is specified with the --grouping option"))

        if "{grouping_name}" not in self.template and self.grouping is not None and not self.global_:
            raise self.parser.error(_("The template does not contain '{grouping_name}' but the --grouping option is active with resetting of group names"))

        if self.ordered is not None and (self.affinity_groups or self.other_groups):
            raise self.parser.error(_("The ``ordered`` option is incompatible with the constraints ``other-groups`` and ``affinity_groups``."))

        df = XlsStudentData.read_target(self.xls_merge)

        if self.grouping is not None:
            self.check_if_present(
                df, self.grouping, file=self.xls_merge, base_dir=self.settings.CWD
            )
            df = df.loc[~df[self.grouping].isnull()]

        if self.other_groups is not None:
            self.check_if_present(
                df, self.other_groups, file=self.xls_merge, base_dir=self.settings.CWD
            )

        if self.affinity_groups is not None:
            self.check_if_present(
                df, self.affinity_groups, file=self.xls_merge, base_dir=self.settings.CWD
            )

        # Shuffled or ordered rows according to `ordered`
        if self.ordered is None:
            df = df.sample(frac=1).reset_index(drop=True)
        elif len(self.ordered) == 0:
            columns = [self.settings.LASTNAME_COLUMN, self.settings.NAME]
            self.check_if_present(df, columns, file=self.xls_merge)
            df = sort_values(df, columns)
        else:
            self.check_if_present(
                df, self.ordered, file=self.xls_merge, base_dir=self.settings.CWD
            )
            df = sort_values(df, self.ordered)

        # Add title to template
        tmpl = self.template
        tmpl = pformat(tmpl, title=self.title)

        # Diviser le dataframe en morceaux d'après `key` et faire des
        # groupes dans chaque morceau
        def df_gen():
            name_gen = self.create_name_gen(tmpl)
            for name, df_group in generate_groupby(df, self.grouping):
                # Reset name generation for a new group
                if not self.global_:
                    name_gen = self.create_name_gen(tmpl)

                # Make sub-groups for group `name`
                yield self.make_groups(name, df_group, name_gen)

        # Concatenate sub-groups for each grouping
        s_groups = pd.concat(df_gen())

        # Add Login column, use index to merge
        df_out = pd.DataFrame({"Login": df[self.settings.LOGIN_COLUMN], "group": s_groups})
        df_out = df_out.sort_values(["group", "Login"])

        with Output(self.target) as out:
            df_out.to_csv(out.target, index=False, header=False)

        df_groups = pd.DataFrame({"groupname": df[self.settings.LOGIN_COLUMN], 'groupingname': s_groups})
        df_groups = df_groups.sort_values(["groupingname", "groupname"])

        csv_target = str(Path(self.target).parent / f"{Path(self.target).stem}_secret.csv")
        with Output(csv_target) as out:
            df_groups.to_csv(out.target, index=False)

        if "MOODLE_ID" in self.settings:
            id = str(self.settings.MOODLE_ID)
        else:
            id = "<MOODLE_ID>"

        url = f"https://moodle.utc.fr/local/userenrols/import.php?id={id}"

        logger.info(_file("CsvCreateGroups_message").format(
            url=url,
            filename=rel_to_dir(self.target, self.settings.UV_DIR),
            title=self.title,
            login=self.settings.LOGIN_COLUMN,
            command_line="guv " + " ".join(map(shlex.quote, sys.argv[1:]))
        ))

    def make_groups(self, name, df, name_gen):
        """Try to make subgroups in dataframe `df`.

        Returns a Pandas series whose index is the one of `df` and
        value is the group name generated from `name` and `name_gen`.

        """

        n = len(df.index)
        partition = self.make_partition(n)

        if self.affinity_groups or self.other_groups:
            partition = self.optimize_partition(name, df, partition)

        names = self.add_names_to_grouping(partition, name, name_gen)
        series = pd.Series(names, index=df.index)

        # Print first and last element when groups are in alphabetical order
        if self.ordered is not None and len(self.ordered) == 0 and self.grouping is None:
            n_groups = max(partition) + 1
            for i in range(n_groups):
                index_i = df.index[partition == i]
                first = df.loc[index_i[0]]
                last = df.loc[index_i[-1]]
                first_name = first[self.settings.NAME_COLUMN]
                first_lastname = first[self.settings.LASTNAME_COLUMN]
                last_name = last[self.settings.NAME_COLUMN]
                last_lastname = last[self.settings.LASTNAME_COLUMN]
                print(f'{series.loc[index_i[0]]} : {first_lastname} {first_name} -- {last_lastname} {last_name} ({len(index_i)})')

        return series

    def add_names_to_grouping(self, partition, name, name_gen):
        """Give names to `groups`"""

        # Number of groups in partition
        num_groups = np.max(partition) + 1

        # Use generator to get templates
        try:
            templates = [next(name_gen) for _ in range(num_groups)]
        except StopIteration as e:
            raise GuvUserError(_("The available group names are exhausted, use # or @ in the template or add names in `--names`.")) from e

        names = np.array([pformat(tmpl, grouping_name=name) for tmpl in templates])
        return names[partition]

    def make_partition(self, n):
        """Return a contiguous partition as an array of integers"""

        if self.proportions is not None:
            proportions = self.proportions
        elif self.group_size is not None:
            size = self.group_size
            if size > 2:
                # When size is > 2, prefer groups of size size-1 rather
                # than groups of size size+1
                n_groups = math.ceil(n / size)
                proportions = np.ones(n_groups)
            else:
                # When size is 2, prefer groups of size 3 rather
                # than groups of size 1
                n_groups = math.floor(n / size)
                proportions = np.ones(n_groups)
        elif self.num_groups is not None:
            proportions = np.ones(self.num_groups)

        return make_groups(n, proportions)

    def optimize_partition(self, name, df, initial_partition):
        """Return an optimized partition given constraints and report"""

        N = len(df.index)

        cooc_data = self.get_cooc_data(df)
        num_permutations = math.ceil(0.4 * N)
        num_variants, best_score, best_partition = evolutionary_algorithm(
            initial_partition,
            cooc_data["cooc_cost"],
            cooc_data["min_cost"],
            max_variants=self.max_iter,
            num_variants=10,
            num_permutations=num_permutations,
            top_k=20
        )

        if best_score == cooc_data["min_cost"]:
            if name is not None:
                logger.info(_("Optimal partition for the group `{name}` found in {num_variants} attempts.").format(name=name, num_variants=num_variants))
            else:
                logger.info(_("Optimal partition found in {num_variants} attempts.").format(num_variants=num_variants))
        else:
            if name is not None:
                logger.warning(_("No optimal solution found for the group `{name}` in {max_iter} attempts, best solution:").format(name=name, max_iter=self.max_iter))
            else:
                logger.warning(_("No optimal solution found in {max_iter} attempts, best solution:").format(max_iter=self.max_iter))

            best_coocurrence = get_coocurrence_matrix_from_array(best_partition)

            for column, weight_coocurrence in cooc_data["cooc_repulse_dict"].items():
                scores = weight_coocurrence * best_coocurrence
                n_errors = (np.sum(scores) - N) // 2
                if n_errors > 0:
                    logger.warning(_("- non-membership constraint by the column `{column}` violated {n_errors} times:").format(column=column, n_errors=n_errors))

                    for i, j in np.column_stack(np.where(scores > 0)):
                        if i >= j:
                            continue
                        columns = [self.settings[e] for e in ["NAME_COLUMN", "LASTNAME_COLUMN"]]
                        stu1 = " ".join(df[columns].iloc[i])
                        stu2 = " ".join(df[columns].iloc[j])
                        logger.warning(f"  - {stu1} -- {stu2}")
                else:
                    logger.warning(_("- non-membership constraint by the column `{column}` verified").format(column=column))

            for column, weight_coocurrence in cooc_data["cooc_affinity_dict"].items():
                scores = (1 - weight_coocurrence) * best_coocurrence
                n_errors = np.sum(scores) // 2

                if n_errors > 0:
                    logger.warning(_("- affinity constraint by the column `{column}` violated {n_errors} times:").format(column=column, n_errors=n_errors))

                    for i, j in np.column_stack(np.where(scores > 0)):
                        if i >= j:
                            continue

                        columns = [self.settings[e] for e in ["NAME_COLUMN", "LASTNAME_COLUMN"]]
                        stu1 = " ".join(df[columns].iloc[i])
                        stu2 = " ".join(df[columns].iloc[j])
                        logger.warning(f"  - {stu1} -- {stu2}")
                else:
                    logger.warning(_("- affinity constraint by the column `{column}` verified").format(column=column))

        return best_partition

    def get_cooc_data(self, df):
        """Return various data to handle group constraints"""

        cooc_repulse_dict = get_coocurrence_dict(df, self.other_groups, nan_policy="different")
        cooc_repulse = sum(cooc for _, cooc in cooc_repulse_dict.items())
        n_repulse = len(self.other_groups)

        cooc_affinity_dict = get_coocurrence_dict(df, self.affinity_groups, nan_policy="same")
        cooc_affinity = sum(cooc for _, cooc in cooc_affinity_dict.items())
        n_affinity = len(self.affinity_groups)

        cooc_final = cooc_repulse - cooc_affinity
        minimum_score = cooc_final.min(axis=None)

        # Final distance matrix: 0 means OK, > 0 means a constraint is violated
        cooc_final = cooc_final - minimum_score
        N = len(df.index)

        diagonal_cost = N * (n_repulse - n_affinity - minimum_score)

        return {
            "cooc_cost": cooc_final,
            "min_cost": diagonal_cost,
            "cooc_repulse_dict": cooc_repulse_dict,
            "cooc_affinity_dict": cooc_affinity_dict
        }

