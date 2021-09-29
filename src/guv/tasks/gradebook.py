"""Ce module rassemble les tâches pour la génération de fichier Excel
pour :

- facilement évaluer un travail par groupe ou non avec un barème ou
  non,
- rassembler les notes pour tenir un jury d'UV.

"""

import math
from collections import OrderedDict
from schema import Schema, And, Use, Or, Optional

import openpyxl
from ..openpyxl_patched import fixit
fixit(openpyxl)

from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment
from openpyxl.styles import PatternFill
from openpyxl.formatting.rule import CellIsRule

from ..openpyxl_utils import (
    frame_range,
    get_address_of_cell,
    get_range_from_cells,
    get_segment,
    row_and_col,
    fit_cells_at_col,
    generate_ranges
)

from . import base_gradebook as baseg
from . import base
from ..utils import sort_values
from .students import XlsStudentDataMerge


def walk_tree(tree, depth=None):
    "Generate coordinates of cells to represent a tree"

    def compute_depth(tree):
        if isinstance(tree, (OrderedDict, dict)):
            return 1 + max(compute_depth(child) for child in tree.values())
        else:
            return 1

    if depth is None:
        depth = compute_depth(tree)

    class RunOut(Exception):
        pass

    def walk_tree0(name, tree, current_depth, nleaves):
        if isinstance(tree, (OrderedDict, dict)):  # Inner node
            current_leaves = 0
            sdepth = None
            x_span = None
            for key, child in tree.items():
                try:
                    yield from walk_tree0(
                        key, child, current_depth + 1, nleaves + current_leaves
                    )
                except RunOut as e:
                    nleaf, sdepth = e.args
                    current_leaves += nleaf
                    x_span = math.ceil(sdepth // (current_depth + 1))
                    sdepth = sdepth - x_span
            if current_depth != 0:
                yield name, nleaves, sdepth, current_leaves, x_span
                raise RunOut(current_leaves, sdepth)
        else:  # Leaf
            x_span = math.ceil((depth + 1) // (current_depth + 1))
            sdepth = depth - x_span
            yield name, nleaves, sdepth, 1, x_span
            raise RunOut(1, sdepth)

    yield from walk_tree0("root", tree, 0, 0)


def get_values(tree, prop, default=1):
    "Return list of terminal values of property"

    if isinstance(tree, dict):
        return [pts for node in tree.values() for pts in get_values(node, prop, default=default)]
    else:
        # Should be a list of dict, concatenating
        a = {}
        for s in tree:
            a.update(s)
        return [a.get(prop, default)]


class MarkingScheme:
    def __init__(self, tree):
        self.tree = tree
        self.width = None
        self.height = None

    @property
    def points(self):
        "Return depth-first list of points"
        return get_values(self.tree, "points")

    @property
    def coeffs(self):
        "Return depth-first list of coeffs"
        return get_values(self.tree, "coeffs")

    def write(self, worksheet, ref):
        row = ref.row
        col = ref.col_idx
        maxi = maxj = -1

        for name, i, j, di, dj in walk_tree(self.tree):
            maxi = max(maxi, i + di)
            maxj = max(maxj, j + dj)
            worksheet.merge_cells(
                start_row=row + i,
                start_column=col + j,
                end_row=row + i + di - 1,
                end_column=col + j + dj - 1,
            )
            worksheet.cell(row=row + i, column=col + j).value = name
            al = Alignment(horizontal="center", vertical="center")
            worksheet.cell(row=row + i, column=col + j).alignment = al

        tree_height = maxi
        tree_width = maxj

        # Columns of coeffs
        ref_coeffs = ref.right(tree_width)
        ref_coeffs.above().text("Coeffs")

        for i, coeff in enumerate(self.coeffs):
            ref_coeffs.below(i).text(coeff)
        self.sum_coeffs = sum(self.coeffs)
        self.coeff_cells = [ref_coeffs.below(i) for i in range(len(self.coeffs))]

        # Columns of points
        ref_points = ref_coeffs.right()
        ref_points.above().text("Points")

        for i, points in enumerate(self.points):
            ref_points.below(i).text(points)
        self.points_cells = [ref_points.below(i) for i in range(len(self.points))]

        ref_points_last = ref_points.below(len(self.points) - 1)

        self.global_total = ref_points_last.below().text(
            "="
            + "+".join(
                "{0} * {1}".format(cell_coeff.coordinate, cell_point.coordinate)
                for cell_point, cell_coeff in zip(self.points_cells, self.coeff_cells)
            )
        )
        ref_points_last.below().left().text("Grade")

        ref_points_last.below(2).text(20)
        ref_points_last.below(2).left().text("Grade /20")

        self.width = tree_width + 2
        self.height = tree_height
        self.bottom_right = worksheet.cell(row + self.height, col + self.width)


class XlsGradeBookNoGroup(baseg.AbstractGradeBook, base.ConfigOpt):
    """Fichier Excel de notes individuelles.

    Cette tâche permet de générer un fichier Excel pour rentrer
    facilement des notes avec un barème détaillé. Le fichier Excel
    peut être divisé en plusieurs feuilles suivant une colonne du
    fichier ``effectifs.xlsx`` et l'argument ``--worksheets`` et
    chaque feuille peut être ordonnée suivant l'argument
    ``--order-by``. Le fichier spécifiant le barème est au format
    YAML. La structure du devoir est spécifiée de manière arborescente
    avec une liste finale pour les questions contenant les points
    accordées à cette question et éventuellement le coefficient (par
    défaut 1) et des détails (ne figurant pas dans le fichier Excel).

    .. code:: yaml

       Exercice 1:
         Question 1:
           - points: 1
       Problème:
         Partie 1:
           Question 1:
             - points: 2
           Question 2:
             - points: 2
             - coeffs: 3
           Question 3:
             - points: 2
             - détails: |
                 Question difficile, ne pas noter trop sévèrement.
         Partie 2:
           Question 1:
             - points: 2
           Question 2:
             - points: 2


    Les notes finales peuvent ensuite être facilement incorporées au
    fichier central en renseignant la variable
    ``AGGREGATE_DOCUMENTS``.

    {options}

    Examples
    --------

    Fichier de notes pour un devoir en divisant par groupe de TD :

    .. code:: bash

       guv xls_grade_book_no_group \\
         --name Devoir1 \\
         --marking-scheme documents/barème_devoir1.yml \\
         --worksheets TD

    avec le fichier YAML contenant par exemple :

    .. code:: yaml

       Exercice 1:
         Question 1:
           - points: 1
       Exercice 2:
         Question 1:
           - points: 1

    Fichier de notes pour une soutenance individuelle en divisant par
    jour de passage (colonne "Jour passage" dans ``effectifs.xlsx``)
    et en ordonnant par ordre de passage (colonne "Ordre passage" dans
    ``effectifs.xlsx``) :

    .. code:: bash

       guv xls_grade_book_no_group \\
         --name Soutenance1 \\
         --marking-scheme documents/barème_soutenance1.yml \\
         --worksheets "Jour passage" \\
         --order-by "Ordre passage"

    avec le fichier YAML contenant par exemple :

    .. code:: yaml

       Fond:
       Forme:

    """

    config_argname = "--marking-scheme"
    config_help = "Fichier contenant le barème détaillé"

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)

    def validate_config(self, config):
        """Validate marking scheme"""

        def validate_subsections(data):
            return Schema(
                Or(
                    And(lambda e: e is None, Use(lambda _: [{}])),
                    [
                        {
                            Optional("points"): Or(int, float),
                            Optional("coeffs"): Or(int, float),
                            Optional("détails"): str,
                        }
                    ],
                    {str: Use(validate_subsections)},
                )
            ).validate(data)

        return Schema({str: Use(validate_subsections)}).validate(config)

    def get_columns(self):
        columns = super().get_columns()

        # Add order_by columns if specified in command line and don't
        # include it in worksheet
        if self.order_by is not None:
            columns.append((self.order_by, "hide", 5))

        if self.group_by is not None:
            columns.append((self.group_by, "raw", 5))

        columns.append((self.name + " brut", "cell", 6))

        return columns


    def add_arguments(self):
        super().add_arguments()

        self.add_argument(
            "-o",
            "--order-by",
            required=False,
            help="Colonne utilisée pour ordonner les noms dans chaque feuille"
        )

        self.add_argument(
            "-w",
            "--worksheets",
            required=False,
            dest="group_by",
            help="Colonne utilisée pour grouper en plusieurs feuilles"
        )

    def create_other_worksheets(self):
        """Create one or more worksheets based on `worksheets` argument."""

        if self.group_by is not None:
            # On groupe avec group_by issu de l'option --worksheets
            gb = self.first_df.sort_values(self.group_by).groupby(
                self.group_by
            )
            for name, group in gb:
                if self.order_by is not None:
                    group = sort_values(group, [self.order_by])

                # Illegal character in sheet name
                name = name.replace("/", " ")
                self.create_worksheet(name, group)
        else:
            group = self.first_df
            if self.order_by is not None:
                group = sort_values(group, [self.order_by])
            self.create_worksheet("grade", group)

    def create_worksheet(self, name, group):
        gradesheet = self.workbook.create_sheet(title=name)

        # Make current worksheet the default one, useful for get_address_of_cell
        self.workbook.active = gradesheet

        ref = gradesheet.cell(3, 1)
        ms = MarkingScheme(self.config)
        ms.write(gradesheet, ref)

        ref = row_and_col(ref, ms.bottom_right)

        # Freeze the structure
        gradesheet.freeze_panes = ref.top()

        def insert_record(ref_cell, record):
            last_name = ref_cell.text(record["Nom"])
            first_name = last_name.below().text(record["Prénom"])
            first_grade = first_name.below()
            last_grade = first_grade.below(ms.height - 1)
            total = last_grade.below()
            total_20 = total.below()

            range = get_range_from_cells(first_grade, last_grade)
            formula = f'=IF(COUNTBLANK({range})>0, "", SUM({range}))'
            total.value = formula

            total_20.text(
                '=IF(ISTEXT(%s),"",%s/%s*20)'
                % (
                    get_address_of_cell(total),
                    get_address_of_cell(total),
                    get_address_of_cell(ms.global_total, absolute=True),
                )
            )

            # Cell in first worksheet
            cell = record[self.name]
            cell.value = "=" + get_address_of_cell(
                total_20, add_worksheet_name=True, absolute=True
            )

            # Total in first worksheet
            cell = record[self.name + " brut"]
            cell.value = "=" + get_address_of_cell(
                total, add_worksheet_name=True, absolute=True
            )

            fit_cells_at_col(last_name, first_name)

        for j, (index, record) in enumerate(group.iterrows()):
            ref_cell = ref.right(j).above(2)
            insert_record(ref_cell, record)


class XlsGradeBookGroup(XlsGradeBookNoGroup):
    """Fichier Excel de notes par groupe.

    Cette tâche permet de créer un fichier Excel pour attribuer des
    notes par groupes évitant ainsi de recopier la note pour chaque
    membre du groupe. Les groupes d'étudiants sont spécifiés par
    l'argument ``--group-by``. Un barème détaillé doit être fourni via
    l'argument ``--marking-scheme``. Le fichier peut être divisé en
    plusieurs feuilles suivant l'argument ``--worksheets`` et chaque
    feuille peut être ordonnée suivant l'argument ``--order-by``.

    Les notes finales peuvent ensuite être facilement incorporées au
    fichier central en renseignant la variable
    ``AGGREGATE_DOCUMENTS``.

    {options}

    """

    config_argname = "--marking-scheme"

    def get_columns(self):
        columns = super().get_columns()
        columns.append((self.subgroup_by, "hide", 5))
        return columns

    def add_arguments(self):
        super().add_arguments()

        self.add_argument(
            "-g",
            "--group-by",
            dest="subgroup_by",
            required=True,
            help="Colonne de groupes utilisée pour noter des groupes d'étudiants"
        )

    def create_worksheet(self, name, group):
        gradesheet = self.workbook.create_sheet(title=name)

        # Write marking scheme
        ref = gradesheet.cell(3, 1)
        ms = MarkingScheme(self.config)
        ms.write(gradesheet, ref)

        # Add room for name and total
        height = ms.height + 4

        # Write each block with write_group_block
        ref = ref.right(ms.width).above(2)

        for subname, subgroup in group.groupby(self.subgroup_by):
            if self.order_by is not None:
                group = group.sort_values(self.order_by)
            bottom_right = self.write_group_block(
                gradesheet, ref, subname, subgroup, height, ms
            )
            frame_range(ref, bottom_right)
            frame_range(ref.below(2), bottom_right)
            ref = row_and_col(ref, bottom_right.right())

    def write_group_block(self, gradesheet, ref_cell, name, group, height, ms):
        # Make current worksheet the default one, useful for get_address_of_cell
        self.workbook.active = gradesheet

        # First column is group column
        group_range = list(get_segment(ref_cell, ref_cell.below(height - 1)))

        # Group name
        group_range[0].text(name).merge(group_range[1]).center()

        # Total of column group
        group_total = group_range[-2]

        formula = '=IFERROR({0},"")'.format(
            "+".join(
                "{1} * IF(ISBLANK({0}), 1/0, {0})".format(
                    get_address_of_cell(group_cell, absolute=True),
                    get_address_of_cell(coeff_cell, absolute=True),
                )
                for group_cell, coeff_cell in zip(group_range[2:-2], ms.coeff_cells)
            )
        )
        group_total.value = formula

        group_total_20 = group_range[-1].text(
            '=IF(ISTEXT({0}),"",{0}/{1}*20)'.format(
                get_address_of_cell(group_total),
                get_address_of_cell(ms.global_total, absolute=True),
            )
        )

        # Next columns are per-student columns
        N = len(group)  # Number of students
        gen = generate_ranges(ref_cell.right(), by="col", length=height, nranges=N)

        # Group student dataframe record and corresponding column range
        for stu_range, (index, record) in zip(gen, group.iterrows()):
            stu_range[0].value = record["Nom"]
            stu_range[1].value = record["Prénom"]

            # Total of student
            stu_total = stu_range[-2]
            formula = '=IFERROR({0},"")'.format(
                "+".join(
                    "{2} * IF(ISBLANK({0}), IF(ISBLANK({1}), 1/0, {1}), {0})".format(
                        get_address_of_cell(stu_cell),
                        get_address_of_cell(group_cell),
                        get_address_of_cell(coeff_cell, absolute=True),
                    )
                    for group_cell, stu_cell, coeff_cell in zip(
                        group_range[2:-2], stu_range[2:-2], ms.coeff_cells
                    )
                )
            )
            stu_total.value = formula

            # Total of student over 20
            stu_total_20 = stu_range[-1]
            stu_total_20.text(
                '=IF(ISTEXT(%s),"",%s/%s*20)'
                % (
                    get_address_of_cell(stu_total),
                    get_address_of_cell(stu_total),
                    get_address_of_cell(ms.global_total, absolute=True),
                )
            )

            record[self.name].value = "=" + get_address_of_cell(
                stu_total_20, add_worksheet_name=True
            )
            record[self.name + " brut"].value = "=" + get_address_of_cell(
                stu_total, add_worksheet_name=True
            )

        return_cell = ref_cell.below(height - 1).right(N)
        return return_cell


class XlsGradeBookJury(baseg.AbstractGradeBook, base.ConfigOpt):
    """Fichier Excel pour la gestion d'un jury d'UV

    Cette tâche permet de générer un classeur regroupant sur la
    première feuille :

    - les notes spécifiées dans le fichier de configuration via
      ``--config`` qui participe à la note finale,
    - une colonne spéciale nommée "Note agrégée" destinée à contenir
      la note agrégée sur 20, charge à vous de la remplir avec une
      formule agrégeant toutes les notes,
    - une note ECTS automatiquement calculée représentant la note
      agrégée.

    La deuxième feuille met à disposition des barres d'admission pour
    chaque note, des barres pour la conversion de la note agrégée en
    note ECTS ainsi que quelques statistiques sur la répartition des
    notes.

    Le fichier de configuration est un fichier au format YAML. Les
    notes devant être utilisées (qu'elles existent ou non dans le
    fichier ``effectifs.xlsx``) sont listées dans la section
    ``marks``. On peut spécifier une note de passage avec ``passing
    mark``. Par défaut, une note de passage de -1 est utilisée mais on
    peut la modifier dans le fichier Excel. Si on souhaite copier ou
    créer une colonne qui n'a pas vocation à contenir une note (et
    donc pas de gestion de note de passage) on doit spécifier le type
    ``raw``.

    .. code:: yaml

       marks:
         - grade1:
             passing mark: 8
         - grade2
         - grade3
         - info:
             type: raw

    La note ECTS et la note agrégée peuvent ensuite être facilement
    incorporées au fichier central en renseignant la variable
    ``AGGREGATE_DOCUMENTS``.

    .. code:: python

       AGGREGATE_DOCUMENTS = [
           [
               "generated/jury_gradebook.xlsx",
               aggregate(
                   left_on="Courriel",
                   right_on="Courriel",
                   subset=["Note agrégée", "Note ECTS"],
               ),
           ]
       ]

    {options}

    Examples
    --------

    .. code:: bash

       guv xls_jury --name SY02_jury --config documents/config_jury.yml

    avec le fichier YAML contenant par exemple :

    .. code:: yaml

       marks:
         - median:
         - final
             passing mark: 6
         - TD:
             type: raw

    """

    config_help = "Fichier de configuration spécifiant les notes à utiliser"

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)

    def get_columns(self, **kwargs):
        # Les colonnes classiques
        columns = [("Nom", "raw", 0), ("Prénom", "raw", 0), ("Courriel", "raw", 0)]

        # Les colonnes nécessaires pour les différents calculs
        columns.append(("Admis", "cell", 0))
        columns.append(("Note admis", "cell", 0))

        # Les colonnes spécifiées dans le fichier de configuration
        for name, props in self.config["columns"].items():
            col_type = props.get("type") if props is not None else None
            columns.append((name, col_type, 0))

        # La colonne de la note finale : A, B, C, D, E, F
        columns.append(("Note ECTS", "cell", 0))

        return columns

    def create_other_worksheets(self):
        self.create_second_worksheet()
        self.update_first_worksheet()

    def validate_config(self, config):
        """Validation du fichier de configuration

        columns:
          grade1:
            type: raw
          grade2:
            type: grade
            note éliminatoire: 8
        options:
        """

        def validate_grade2(data):
            if data.get("type", "grade") == "grade":
                schema = Schema(
                    {
                        Optional("type", default="grade"): "grade",
                        Optional("passing mark", default=-1): -1,
                        Optional(str): object,
                    }
                )
            else:
                schema = Schema(
                    {"type": Or("raw", "hide", "cell"), Optional(str): object,}
                )
            return schema.validate(data)

        validate_grade = Schema(
            Or(
                And(
                    Or(None, {}, ""),
                    Use(lambda dummy: {"type": "grade", "passing mark": -1}),
                ),
                And(dict, Use(validate_grade2)),
            )
        )

        DEFAULT_MARKS = {"Note agrégée": {"type": "grade", "passing mark": -1}}

        validate_marks = Or(
            And(Or(None, {}, ""), Use(lambda dummy: DEFAULT_MARKS)),
            {
                Optional("Note agrégée", default=DEFAULT_MARKS["Note agrégée"]): {},
                Optional(str): validate_grade,
            },
        )

        DEFAULT_OPTIONS = {
            "Percentile note A": 0.9,
            "Percentile note B": 0.65,
            "Percentile note C": 0.35,
            "Percentile note D": 0.1,
        }

        validate_options = Or(
            And(Or(None, {}, ""), Use(lambda dummy: DEFAULT_OPTIONS)),
            {
                "Percentile note A": float,
                "Percentile note B": float,
                "Percentile note C": float,
                "Percentile note D": float,
                Optional(str): object,
            },
            {Optional(str): object},
        )

        sc = Schema(
            Or(
                And(
                    None,
                    Use(
                        lambda dummy: {
                            "marks": validate_marks.validate(None),
                            "options": validate_options.validate(None),
                        }
                    ),
                ),
                {
                    Optional(
                        "marks", default=validate_marks.validate(None)
                    ): validate_marks,
                    Optional(
                        "options", default=validate_options.validate(None)
                    ): validate_options,
                },
            )
        )

        # Validate config
        validated_config = sc.validate(config)

        # Validation does not preserve order
        old_columns = validated_config["columns"].copy()
        new_columns = {}
        for name in list(config["columns"].keys()):
            new_columns[name] = old_columns.pop(name)
        new_columns.update(old_columns)
        validated_config["columns"] = new_columns

        return validated_config

    @property
    def grade_columns(self):
        """Colonnes associées à des notes"""

        for name, props in self.config["columns"].items():
            if props["type"] == "grade":
                props2 = props.copy()
                del props2["type"]
                yield name, props2

    def write_key_value_props(self, ref_cell, title, props):
        "Helper function to write key-value table"

        keytocell = {}
        ref_cell.text(title).merge(ref_cell.right()).style = "Pandas"
        for key, value in props.items():
            ref_cell = ref_cell.below()
            ref_cell.value = key
            ref_cell.right().value = value
            keytocell[key] = ref_cell.right()
        return ref_cell.right(), keytocell

    def create_second_worksheet(self):
        # Write new gradesheet
        self.gradesheet = self.workbook.create_sheet(title="Paramètres")
        self.workbook.active = self.gradesheet
        current_cell = self.gradesheet.cell(row=1, column=1)

        # Write option blocks for grade columns
        self.grades_options = {}
        for name, props in self.grade_columns:
            # Write key-value table
            lower_right, keytocell = self.write_key_value_props(
                current_cell, name, props
            )
            self.grades_options[name] = keytocell
            current_cell = lower_right.below(2).left(1)

        # Add default global options block
        options = self.config.get("options", {})
        for ects, grade in zip("ABCD", [0.9, 0.65, 0.35, 0.1]):
            if ("Percentile note " + ects) not in options:
                options["Percentile note " + ects] = grade

        lower_right, self.global_options = self.write_key_value_props(
            current_cell, "Options globales", options
        )
        current_cell = lower_right.below(2).left(1)

        # On écrit les seuils des notes correspondants aux percentiles choisis
        props = {}
        for i, ects in enumerate("ABCD"):
            percentile_cell = self.global_options["Percentile note " + ects]
            props[
                ects + " si >="
            ] = "=IF(ISERROR(PERCENTILE({0}, {1})), NA(), PERCENTILE({0}, {1}))".format(
                self.get_column_range("Note admis"),
                get_address_of_cell(percentile_cell),
            )

        lower_right, percentiles_theo = self.write_key_value_props(
            current_cell, "Percentiles théoriques", props
        )
        current_cell = lower_right.below(2).left(1)

        # Percentiles effectifs
        props = {}
        for i, ects in enumerate("ABCD"):
            props[ects + " si >="] = "=" + get_address_of_cell(
                percentiles_theo[ects + " si >="]
            )

        lower_right, self.percentiles_used = self.write_key_value_props(
            current_cell, "Percentiles utilisés", props
        )
        current_cell = lower_right.below(2).left(1)

        # On écrit les proportions de notes ECTS en fonction de la
        # colonne `Admis`
        ref_cell = self.gradesheet.cell(row=1, column=4)
        props = {}
        for ects in "ABCDEF":
            props["Nombre de " + ects] = ('=COUNTIF({}, "{}")').format(
                self.get_column_range("Note ECTS"), ects
            )
        props["Nombre d'admis"] = '=SUMIF({}, "<>#N/A")'.format(
            self.get_column_range("Admis")
        )
        props["Effectif total"] = "=COUNTA({})".format(self.get_column_range("Admis"))
        props["Ratio"] = '=AVERAGEIF({}, "<>#N/A")'.format(
            self.get_column_range("Admis")
        )
        lower_right, statistiques = self.write_key_value_props(
            ref_cell, "Statistiques", props
        )

    def update_first_worksheet(self):
        # Pour que get_address_of_cell marche correctement
        self.workbook.active = self.first_ws

        # On écrit la colonne "Admis" des admis/refusés basée sur les
        # barres
        for i, (index, record) in enumerate(self.first_df.iterrows()):
            # Teste si une des notes est vide
            any_blank_cell = "OR({})".format(
                ", ".join(
                    "ISBLANK({})".format(get_address_of_cell(record[name]))
                    for name, props in self.grade_columns
                )
            )

            # Teste si toutes les barres sont atteintes
            above_all_threshold = "AND({})".format(
                ", ".join(
                    "IF(ISNUMBER({0}), {0}>={1}, 1)".format(
                        get_address_of_cell(record[name]),
                        get_address_of_cell(
                            self.grades_options[name]["Note éliminatoire"],
                            absolute=True,
                        ),
                    )
                    for name, props in self.grade_columns
                )
            )

            # NA() s'il y a un problème, 0 si recalé, 1 si reçu
            formula = f"=IFERROR(IF({any_blank_cell}, NA(), IF({above_all_threshold}, 1, 0)), NA())"
            record["Admis"].value = formula

        # On écrit la note agrégée des admis dans la colonne "Note
        # admis" pour faciliter le calcul des percentiles sur les
        # admis
        for i, (index, record) in enumerate(self.first_df.iterrows()):
            record["Note admis"].value = '=IFERROR(IF({}=1, {}, ""), "")'.format(
                get_address_of_cell(record["Admis"]),
                get_address_of_cell(record["Note agrégée"]),
            )

        # On écrit la note ECTS en fonction de la note agrégée et des
        # percentiles utilisés
        perc_A = get_address_of_cell(self.percentiles_used["A si >="], absolute=True)
        perc_B = get_address_of_cell(self.percentiles_used["B si >="], absolute=True)
        perc_C = get_address_of_cell(self.percentiles_used["C si >="], absolute=True)
        perc_D = get_address_of_cell(self.percentiles_used["D si >="], absolute=True)
        percs = dict(perc_A=perc_A, perc_B=perc_B, perc_C=perc_C, perc_D=perc_D)

        for i, (index, record) in enumerate(self.first_df.iterrows()):
            note_admis = get_address_of_cell(record["Admis"])
            note_agregee = get_address_of_cell(record["Note agrégée"])
            opts = dict(note_admis=note_admis, note_agregee=note_agregee)
            opts.update(percs)

            # Fonction pour la construction des IF imbriqués
            def switch(ifs, default):
                if ifs:
                    cond, then = ifs[0]
                    return "IF({cond}, {then}, {else_})".format(
                        cond=cond.format(**opts),
                        then=then,
                        else_=switch(ifs[1:], default),
                    )
                else:
                    return default

            # Formule de type switch/case
            formula = switch(
                (
                    ("ISNA({note_admis})", "NA()"),
                    ('{note_agregee}="RESERVE"', '"RESERVE"'),
                    ('{note_agregee}="ABS"', '"ABS"'),
                    ("{note_admis}=0", '"F"'),
                    ("{note_agregee}>={perc_A}", '"A"'),
                    ("{note_agregee}>={perc_B}", '"B"'),
                    ("{note_agregee}>={perc_C}", '"C"'),
                    ("{note_agregee}>={perc_D}", '"D"'),
                ),
                '"E"',
            )

            record["Note ECTS"].value = "=" + formula

        # On centre les notes ECTS
        for cell in self.first_df["Note ECTS"]:
            cell.alignment = Alignment(horizontal="center")

        # On colore la cellule en fonction de la note ECTS
        range = self.get_column_range("Note ECTS")
        for ects, color in zip(
            "ABCDEF", ["00FF00", "C2FF00", "F7FF00", "FFC100", "FF6900", "FF0000"]
        ):
            fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            rule = CellIsRule(operator="equal", formula=[f'"{ects}"'], fill=fill)
            self.first_ws.conditional_formatting.add(range, rule)

        # Formattage conditionnel pour les notes éliminatoires
        red_fill = PatternFill(
            start_color="EE1111", end_color="EE1111", fill_type="solid"
        )

        for name, opts in self.grades_options.items():
            threshold_cell = opts["Note éliminatoire"]
            threshold_addr = get_address_of_cell(threshold_cell, compat=True)
            self.first_ws.conditional_formatting.add(
                self.get_column_range(name),
                CellIsRule(
                    operator="lessThan", formula=[threshold_addr], fill=red_fill
                ),
            )

        # On offre la possibilité de trier
        max_column = self.first_ws.max_column
        max_row = self.first_ws.max_row
        self.first_ws.auto_filter.ref = "A1:{}{}".format(
            get_column_letter(max_column), max_row
        )
        range = self.get_column_range("Note ECTS")
        self.first_ws.auto_filter.add_sort_condition(range)
