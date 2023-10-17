"""Ce module rassemble les tâches pour la génération de fichier Excel
pour :

- facilement évaluer un travail par groupe ou non avec un barème ou
  non,
- rassembler les notes pour tenir un jury d'UV.

"""

import json
import math
import os
import textwrap
from collections import OrderedDict

import guv
import jsonschema
import openpyxl
import yaml

from ..openpyxl_patched import fixit

fixit(openpyxl)

from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils import get_column_letter

from ..openpyxl_utils import (fit_cells_at_col, frame_range, generate_ranges,
                              get_address_of_cell, get_range_from_cells,
                              get_segment, row_and_col)
from ..utils import sort_values
from ..utils_ask import checkboxlist_prompt, prompt_number
from ..utils_config import rel_to_dir, ask_choice
from . import base
from . import base_gradebook as baseg


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
        self.coeff_cells = None
        self.points_cells = None

    @property
    def points(self):
        "Return depth-first list of points"
        return get_values(self.tree, "points")

    @property
    def coeffs(self):
        "Return depth-first list of coeffs"
        return get_values(self.tree, "coeff")

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

        # Column of coeffs
        ref_coeffs = ref.right(tree_width)
        ref_coeffs.above().text("Coeffs")

        for i, coeff in enumerate(self.coeffs):
            ref_coeffs.below(i).text(coeff)
        self.sum_coeffs = sum(self.coeffs)
        self.coeff_cells = [ref_coeffs.below(i) for i in range(len(self.coeffs))]

        # Column of points
        ref_points = ref_coeffs.right()
        ref_points.above().text("Points")

        for i, points in enumerate(self.points):
            ref_points.below(i).text(points)
        self.points_cells = [ref_points.below(i) for i in range(len(self.points))]

        ref_points_last = ref_points.below(len(self.points) - 1)

        self.global_total = ref_points_last.below(2).text(
            "="
            + "+".join(
                "{0} * {1}".format(cell_coeff.coordinate, cell_point.coordinate)
                for cell_point, cell_coeff in zip(self.points_cells, self.coeff_cells)
            )
        )
        self.global_total_rescale = ref_points_last.below(3).text(20)

        ref_points_last.below(2).left().text("Grade")
        ref_points_last.below(3).left().text("Grade /20")

        self.width = tree_width + 2
        self.height = tree_height
        self.bottom_right = worksheet.cell(row + self.height, col + self.width)


class XlsGradeBookNoGroup(baseg.AbstractGradeBook, base.ConfigOpt):
    """Fichier Excel de notes individuelles.

    Cette tâche permet de générer un fichier Excel pour rentrer facilement des
    notes avec un barème détaillé. Le fichier Excel peut être divisé en
    plusieurs feuilles de calculs selon une colonne du fichier
    ``effectifs.xlsx`` via l'argument ``--worksheets``. Dans chacune de ces
    feuilles, les étudiants peuvent être ordonnés suivant l'argument
    ``--order-by``. Le chemin vers un fichier de barème détaillé peut être
    fourni via l'argument ``--marking-scheme``. S'il n'est pas fourni le barème
    sera demandé interactivement. Le fichier de barème doit être au format YAML.
    La structure du devoir est spécifiée de manière arborescente avec une liste
    finale pour les questions contenant les points accordés à cette question et
    éventuellement le coefficient (par défaut 1) et des détails (ne figurant pas
    dans le fichier Excel). Par exemple :

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
             - coeff: 3
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
    fichier central en renseignant la variable ``DOCS``.

    {options}

    Examples
    --------

    - Fichier de notes avec un barème à définir interactivement sur une seule
      feuille Excel :

      .. code:: bash

         guv xls_grade_book_no_group --name Devoir1

    - Fichier de notes pour un devoir en divisant par groupe de TD :

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

    - Fichier de notes pour une soutenance individuelle en divisant
      par jour de passage (colonne "Jour passage" dans
      ``effectifs.xlsx``) et en ordonnant par ordre de passage
      (colonne "Ordre passage" dans ``effectifs.xlsx``) :

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
    config_required = False

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)

    def ask_config(self):
        def ask_subitem(item_name=None):
            subitems = {}
            if item_name is not None:
                prompt = f"Nom d'une sous-question de `{item_name}` ? "
            else:
                prompt = "Nom d'une sous-question ? "

            name = input(prompt)
            if name:
                if item_name is not None:
                    prompt = f"Nom d'une autre sous-question de `{item_name}` ? "
                else:
                    prompt = "Nom d'une autre sous-question ? "

                subitems[name] = ask_subitem(item_name=name)
                while True:
                    name = input(prompt)
                    if name:
                        subitems[name] = ask_subitem(item_name=name)
                    else:
                        break
            else:
                points = prompt_number(f"Points pour la sous-question `{item_name}` : ", default="1")
                coeff = prompt_number(f"Coefficient pour la sous-question `{item_name}` : ", default="1")
                subitems = [{"points": points, "coeff": coeff}]

            return subitems

        while True:
            config = ask_subitem()
            print("Fichier YAML construit :")
            print(yaml.dump(config))
            result = ask_choice("Valider ? (y/n) ", {"y": True, "n": False})
            if result:
                break

        return self.validate_config(config)

    def validate_config(self, config):
        """Validation du fichier de configuration"""

        tmpl_dir = os.path.join(guv.__path__[0], "schemas")
        schema_file = os.path.join(tmpl_dir, "gradebook_marking_schema.json")
        schema = json.load(open(schema_file, "rb"))

        jsonschema.validate(config, schema)

        def set_default(elt):
            if isinstance(elt, dict):
                for key, value in elt.items():
                    if value is None:
                        elt[key] = [{
                            "points": 1,
                            "coeff": 1
                        }]
                    else:
                        set_default(value)
            elif isinstance(elt, list):
                if all("points" not in d for d in elt):
                    elt.append({"points": 1})
                if all("coeff" not in d for d in elt):
                    elt.append({"coeff": 1})
            else:
                raise RuntimeError

        set_default(config)

        return config

    def get_columns(self):
        columns = super().get_columns()

        # Add order_by column if specified in command line and don't include it
        # in worksheet
        if self.order_by is not None:
            columns.append((self.order_by, "hide", 5))

        if self.extra_cols is not None:
            for colname in self.extra_cols:
                columns.append((colname, "raw", 6))

        if self.group_by is not None:
            columns.append((self.group_by, "raw", 6))

        columns.append((self.name + " brut", "cell", 7))

        self.agg_colname = self.name

        return columns

    def add_arguments(self):
        super().add_arguments()

        self.add_argument(
            "-o",
            "--order-by",
            metavar="colname",
            required=False,
            help="Colonne utilisée pour ordonner les noms dans chaque feuille"
        )

        self.add_argument(
            "-w",
            "--worksheets",
            required=False,
            metavar="colname",
            dest="group_by",
            help="Colonne utilisée pour grouper en plusieurs feuilles"
        )

        self.add_argument(
            "-e",
            "--extra-cols",
            nargs="+",
            metavar="colname",
            required=False,
            help="Colonnes supplémentaires à inclure dans la feuille de notes"
        )

    def create_other_worksheets(self):
        """Create one or more worksheets based on `worksheets` argument."""

        if self.group_by is not None:
            # On groupe avec group_by issu de l'option --worksheets
            gb = self.first_df.sort_values(self.group_by).groupby(
                self.group_by
            )
            for name, group in gb:
                order_by = self.order_by if self.order_by is not None else "Nom"
                group = sort_values(group, [order_by])

                # Illegal character in sheet name
                name = name.replace("/", " ")
                self.create_worksheet(name, group)
        else:
            group = self.first_df
            order_by = self.order_by if self.order_by is not None else "Nom"
            group = sort_values(group, [order_by])
            self.create_worksheet("grade", group)

    def create_worksheet(self, name, group):
        gradesheet = self.workbook.create_sheet(title=name)

        # Make current worksheet the default one, useful for get_address_of_cell
        self.workbook.active = gradesheet

        # Leave room from statistics
        ref_stats = gradesheet.cell(4, 2)
        formula = '=IF(ISERROR(QUARTILE({{marks_range}}, {num})), "", QUARTILE({{marks_range}}, {num}))'
        stats = [
            (name, formula.format(num=num))
            for name, num in (("Min", 0), ("Q1", 1), ("médiane", 2), ("Q3", 3), ("Max", 4))
        ]
        ref_marking_scheme = ref_stats.right(len(stats))

        ms = MarkingScheme(self.config)
        ms.write(gradesheet, ref_marking_scheme)
        ref = row_and_col(ref_marking_scheme, ms.bottom_right)

        # Freeze the structure
        gradesheet.freeze_panes =  ref.top()

        def insert_record(ref_cell, i, record):
            index = ref_cell.text(str(i) + ".")
            last_name = index.below().text(record["Nom"])
            first_name = last_name.below().text(record["Prénom"])
            first_grade = first_name.below()
            last_grade = first_grade.below(ms.height - 1)
            total = last_grade.below(2)
            total_20 = total.below()

            marks_range = get_range_from_cells(first_grade, last_grade)
            cells = get_segment(first_grade, last_grade)

            formula = '=IF(COUNTBLANK({marks_range}) > 0, "", {formula})'.format(
                marks_range=marks_range,
                formula=" + ".join(
                    "{mark} * {coeff}".format(
                        mark=get_address_of_cell(group_cell),
                        coeff=get_address_of_cell(coeff_cell, absolute=True),
                    )
                    for group_cell, coeff_cell in zip(cells, ms.coeff_cells)
                )
            )
            total.value = formula

            total_20.text(
                '=IF(ISTEXT({stu_total}),"",{stu_total}/{global_total}*{rescaling})'.format(
                    stu_total=get_address_of_cell(total),
                    global_total=get_address_of_cell(ms.global_total, absolute=True),
                    rescaling=get_address_of_cell(ms.global_total_rescale, absolute=True)
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

            return total_20

        for j, (index, record) in enumerate(group.iterrows()):
            ref_cell = ref.right(j).above(3)
            last_cell = insert_record(ref_cell, j + 1, record)

        # Add statistics of grades
        for i, (first, last) in enumerate(zip(
            get_segment(ref, row_and_col(last_cell, ref)),
            get_segment(row_and_col(ref, last_cell), last_cell),
        )):
            marks_range = get_range_from_cells(first, last)
            for j, (name, formula) in enumerate(stats):
                if i == 0:
                    ref_stats.right(j).below(-1).text(name).center()
                ref_stats.right(j).below(i).text(formula.format(marks_range=marks_range))


        # Around grades
        frame_range(ref.above(3), last_cell.above(3))

        # Around totals
        frame_range(ref.below(ms.height + 1), last_cell)


class XlsGradeBookGroup(XlsGradeBookNoGroup):
    """Fichier Excel de notes par groupe.

    Cette tâche permet de créer un fichier Excel pour attribuer des notes par
    groupes évitant ainsi de recopier la note pour chaque membre du groupe. Les
    groupes d'étudiants sont spécifiés par l'argument ``--group-by``. Un barème
    détaillé peut être fourni via l'argument ``--marking-scheme``. S'il n'est
    pas fourni, un barème sera demandé interactivement. Le fichier peut être
    divisé en plusieurs feuilles suivant l'argument ``--worksheets`` et chaque
    feuille peut être ordonnée suivant l'argument ``--order-by``.

    Le fichier spécifiant le barème est au format YAML. La structure
    du devoir est spécifiée de manière arborescente avec une liste
    finale pour les questions contenant les points accordés à cette
    question et éventuellement le coefficient (par défaut 1) et des
    détails (ne figurant pas dans le fichier Excel). Par exemple :

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
             - coeff: 3
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
    ``DOCS``.

    {options}

    Examples
    --------

    Fichier de notes par groupe de projet :

    .. code:: bash

       guv xls_grade_book_group \\
         --name Devoir1 \\
         --marking-scheme documents/barème_devoir1.yml \\
         --group-by 'Groupe Projet'

    avec le fichier YAML contenant par exemple :

    .. code:: yaml

       Exercice 1:
         Question 1:
           - points: 1
       Exercice 2:
         Question 1:
           - points: 1

    """

    config_argname = "--marking-scheme"

    def get_columns(self):
        columns = super().get_columns()
        columns.append((self.subgroup_by, "raw", 5))
        return columns

    def add_arguments(self):
        super().add_arguments()

        self.add_argument(
            "-g",
            "--group-by",
            dest="subgroup_by",
            metavar="colname",
            required=True,
            help="Colonne de groupes utilisée pour noter des groupes d'étudiants"
        )

    def create_worksheet(self, name, group):
        gradesheet = self.workbook.create_sheet(title=name)

        # Write marking scheme
        ref = gradesheet.cell(4, 2)
        ms = MarkingScheme(self.config)
        ms.write(gradesheet, ref)

        # Add room for name and total
        height = ms.height + 6

        # Write each block with write_group_block
        ref = ref.right(ms.width).above(3)

        # Freeze the structure
        gradesheet.freeze_panes = ref.top()

        for i, (subname, subgroup) in enumerate(group.groupby(self.subgroup_by)):
            if self.order_by is not None:
                group = group.sort_values(self.order_by)
            bottom_right = self.write_group_block(
                gradesheet, ref, i, subname, subgroup, height, ms
            )

            # Around grades
            frame_range(ref, bottom_right.above(3))

            # Around totals
            frame_range(ref.below(height - 2), bottom_right)

            ref = row_and_col(ref, bottom_right.right())

    def write_group_block(self, gradesheet, ref_cell, i, name, group, height, ms):
        # Make current worksheet the default one, useful for get_address_of_cell
        self.workbook.active = gradesheet

        # First column is group column
        group_range = list(get_segment(ref_cell, ref_cell.below(height - 1)))

        # Number
        group_range[0].text(str(i+1) + ".")

        # Group name
        group_range[1].text(name).merge(group_range[2]).center()

        # Total of column group
        group_total = group_range[-2]

        formula = '=IFERROR({0},"")'.format(
            "+".join(
                "{1} * IF(ISBLANK({0}), 1/0, {0})".format(
                    get_address_of_cell(group_cell, absolute=True),
                    get_address_of_cell(coeff_cell, absolute=True),
                )
                for group_cell, coeff_cell in zip(group_range[3:-2], ms.coeff_cells)
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
            stu_range[1].value = record["Nom"]
            stu_range[2].value = record["Prénom"]

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
                        group_range[3:-3], stu_range[3:-3], ms.coeff_cells
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
      ``--config`` qui participent à la note finale,
    - une colonne spéciale nommée "Note agrégée" contenant une note sur 20 avec
      une formule par défaut utilisant les coefficients et les notes maximales
      renseignées dans le fichier de configuration,
    - une note ECTS (ABCDEF) automatiquement calculée représentant la note
      agrégée en fonction de percentiles,
    - d'autres colonnes utiles pour le jury et qui ne sont pas des notes.

    La deuxième feuille met à disposition des barres d'admission pour chaque
    note, les coefficients de chaque note, les notes maximales pour chaque note
    ainsi que les barres pour la conversion de la note agrégée en note ECTS
    ainsi que quelques statistiques sur la répartition des notes.

    Le fichier de configuration est un fichier au format YAML. Les notes devant
    être utilisées (qu'elles existent ou non dans le fichier ``effectifs.xlsx``)
    sont listées dans la section ``grades``. On doit spécifier le nom de la
    colonne avec ``name`` et optionnellement :

    - une barre de passage avec ``passing grade``, par défaut -1,
    - un coefficient avec ``coefficient``, par défaut 1,
    - une note maximale avec ``maximum grade``, par défaut 20,

    Les colonnes qui ne sont pas des notes peuvent être spécifiées avec
    ``others``. Par exemple :

    .. code:: yaml

       grades:
         - name: grade1
           passing grade: 8
           coefficient: 2
         - name: grade2
         - name: grade3
       others:
         - info

    La note ECTS et la note agrégée peuvent ensuite être facilement
    incorporées au fichier central en renseignant la variable
    ``DOCS``.

    .. code:: python

       DOCS.aggregate_jury("generated/jury_gradebook.xlsx")

    {options}

    Examples
    --------

    - Feuille de notes avec la note ``median``, la note ``final`` avec
      une barre à 6 et l'information ``Branche`` :

      .. code:: bash

         guv xls_grade_book_jury --name SY02_jury --config documents/config_jury.yml

      avec le fichier YAML contenant par exemple :

      .. code:: yaml

         grades:
           - name: median
             coefficient: .4
           - name: final
             coefficient: .6
             passing grade: 6
         others:
           - Branche

    """

    config_help = "Fichier de configuration spécifiant les notes à utiliser"
    config_required = False

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)

    def message(self, target):
        return textwrap.dedent("""\

        Pour agréger les notes au fichier central `effectifs.xlsx`, ajouter :

        DOCS.aggregate_jury("{filename}")

        dans le fichier `config.py` de l'UV/UE.

        Pour ensuite pouvoir charger les notes ECTS sur l'ENT :

        guv csv_for_upload -g "Note ECTS" --ects

        """.format(**{"filename": rel_to_dir(target, self.settings.UV_DIR)}))

    def get_columns(self, **kwargs):
        # Les colonnes classiques
        columns = [("Nom", "raw", 0), ("Prénom", "raw", 0), ("Courriel", "raw", 0)]

        # Les colonnes nécessaires pour les différents calculs
        columns.append(("Admis", "cell", 2))
        columns.append(("Note admis", "cell", 2))

        # Les colonnes spécifiées dans le fichier de configuration
        for grade in self.config["grades"]:
            name = grade["name"]
            columns.append((name, "cell", 3))

        for other in self.config["others"]:
            columns.append((other, "raw", 1))

        # La colonne de la note finale : A, B, C, D, E, F
        columns.append(("Note ECTS", "cell", 4))

        self.agg_colname = ["Note agrégée", "Note ECTS"]

        return columns

    def create_other_worksheets(self):
        self.create_second_worksheet()
        self.update_first_worksheet()

    def ask_config(self):
        cols = self.data_df.columns.values.tolist()

        grade_cols = cols.copy()
        for c in [
            "Nom",
            "Prénom",
            "Date de naissance",
            "Dernier diplôme obtenu",
            "Courriel",
            "Login",
            "Tel. 1",
            "Tel. 2",
            "Branche",
            "Semestre",
            "Prénom_moodle",
            "Nom_moodle",
            "Numéro d'identification",
            "Adresse de courriel",
            "Cours",
            "TD",
            "TP"
        ]:
            if c in grade_cols:
                grade_cols.remove(c)

        grades = checkboxlist_prompt(
            "Indiquer les colonnes contenants des notes (SPACE: sélectionner, ENTER: valider):",
            [(c, c) for c in grade_cols]
        )
        grades_props = []
        for grade in grades:
            props = {"name": grade}
            props["coefficient"] = prompt_number(f"Coefficient for {grade}: ", default="1")
            props["passing grade"] = prompt_number(f"Passing grade for {grade}: ", default="-1")
            grades_props.append(props)

        other_cols = cols.copy()
        for c in ["Nom", "Prénom", "Courriel",]:
            if c in other_cols:
                other_cols.remove(c)
        for c in grades:
            other_cols.remove(c)

        others = checkboxlist_prompt(
            "Indiquer d'autres colonnes :",
            [(c, c) for c in other_cols]
        )

        return self.validate_config({
            "grades": grades_props,
            "others": others
        })

    def validate_config(self, config):
        """Validation du fichier de configuration

        grades:
          - name: grade1
            passing grade: 8
            coefficient: 2
          - name: grade2
          - name: grade3
        others:
          - info
        """

        tmpl_dir = os.path.join(guv.__path__[0], "schemas")
        schema_file = os.path.join(tmpl_dir, "gradebook_jury_schema.json")
        schema = json.load(open(schema_file, "rb"))

        jsonschema.validate(config, schema)

        # Add default value in grades
        if "Percentile A" not in config:
            config["Percentile note A"] = .9
        if "Percentile note B" not in config:
            config["Percentile note B"] = .65
        if "Percentile note C" not in config:
            config["Percentile note C"] = .35
        if "Percentile note D" not in config:
            config["Percentile note D"] = .1

        for grade in config["grades"]:
            if "coefficient" not in grade:
                grade["coefficient"] = 1
            if "maximum grade" not in grade:
                grade["maximum grade"] = 20
            if "passing grade" not in grade:
                grade["passing grade"] = -1

        config["grades"].append({
            "name": "Note agrégée",
            "passing grade": -1
        })

        if "others" not in config:
            config["others"] = []

        return config

    @property
    def grade_columns(self):
        """Colonnes associées à des notes"""

        for props in self.config["grades"]:
            props2 = props.copy()
            name = props2["name"]
            del props2["name"]
            yield name, props2

    def write_key_value_props(self, ref_cell, title, props):
        """Helper function to write key-value table.

        Written at `ref_cell` with header `title` and key-value in `props`.
        Return lower-right cell and dictionary of property name to actual cell.

        """

        keytocell = {}
        ref_cell.text(title).merge(ref_cell.right()).style = "Pandas"
        current_cell = ref_cell
        for key, value in props.items():
            current_cell = current_cell.below()
            current_cell.value = key
            current_cell.right().value = value
            keytocell[key] = current_cell.right()

        frame_range(ref_cell, current_cell.right())
        return current_cell.right(), keytocell

    def create_second_worksheet(self):
        # Write new gradesheet
        self.gradesheet = self.workbook.create_sheet(title="Paramètres")
        self.workbook.active = self.gradesheet
        current_cell = self.gradesheet.cell(row=1, column=1)

        # Write option blocks for grade columns
        self.grades_options = {}
        for name, props in self.grade_columns:
            # Add some stats on marks
            for stat, q in (("Min", 0), ("Q1", 1), ("Médiane", 2), ("Q3", 3), ("Max", 4)):
                props[stat] = '=IF(ISERROR(QUARTILE({0}, 0)), NA(), QUARTILE({0}, {1}))'.format(
                    self.get_column_range(name),
                    q
                )

            # Write key-value table
            keys = ["name", "passing grade", "coefficient", "maximum grade"]
            ordered_props = {k: props[k] for k in keys if k in props}
            rest = {k: props[k] for k in props if k not in keys}
            lower_right, keytocell = self.write_key_value_props(
                current_cell, name, ordered_props | rest
            )
            self.grades_options[name] = keytocell
            current_cell = current_cell.right(3)

        # Maximum number of options
        max_height = max(len(v) for k, v in self.grades_options.items())

        # Add default global options block
        current_cell = self.gradesheet.cell(row=max_height + 4, column=1)
        options = self.config.copy()
        del options["grades"]
        if "others" in options:
            del options["others"]
        lower_right, self.global_options = self.write_key_value_props(
            current_cell, "Options globales", options
        )
        current_cell = current_cell.right(3)

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
        current_cell = current_cell.right(3)

        # Percentiles effectifs
        props = {}
        for i, ects in enumerate("ABCD"):
            props[ects + " si >="] = "=" + get_address_of_cell(
                percentiles_theo[ects + " si >="]
            )

        lower_right, self.percentiles_used = self.write_key_value_props(
            current_cell, "Percentiles utilisés", props
        )
        current_cell = current_cell.right(3)

        # On écrit les proportions de notes ECTS en fonction de la
        # colonne `Admis`
        props = {}
        for ects in "ABCDEF":
            props["Nombre de " + ects] = ('=COUNTIF({}, "{}")').format(
                self.get_column_range("Note ECTS"), ects
            )
        props["Nombre d'admis"] = '=SUMIF({}, "<>#N/A")'.format(
            self.get_column_range("Admis")
        )
        props["Effectif total"] = "=COUNTA({})".format(self.get_column_range("Admis"))
        props["Ratio"] = '=IF(ISERROR(AVERAGEIF({0}, "<>#N/A")), NA(), AVERAGEIF({0}, "<>#N/A"))'.format(
            self.get_column_range("Admis")
        )
        lower_right, statistiques = self.write_key_value_props(
            current_cell, "Statistiques", props
        )

    def update_first_worksheet(self):
        # Pour que get_address_of_cell marche correctement
        self.workbook.active = self.first_ws

        # On écrit la note agrégée basée sur la note maximum et le coefficient
        # de chaque note
        coef_sum = "+".join(
            get_address_of_cell(
                self.grades_options[name]["coefficient"],
                absolute=True,
            )
            for name, props in self.grade_columns
            if name != "Note agrégée"
        )

        for i, (index, record) in enumerate(self.first_df.iterrows()):
            formula = "=(" + "+".join(
                "{coef}*{grade}/{grade_max}*20".format(
                    coef=get_address_of_cell(
                        self.grades_options[name]["coefficient"],
                        absolute=True,
                    ),
                    grade=get_address_of_cell(record[name]),
                    grade_max=get_address_of_cell(
                        self.grades_options[name]["maximum grade"],
                        absolute=True,
                    ),
                )
                for name, props in self.grade_columns
                if name != "Note agrégée"
            ) + f")/({coef_sum})"

            record["Note agrégée"].value = formula

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
                            self.grades_options[name]["passing grade"],
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
            threshold_cell = opts["passing grade"]
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
