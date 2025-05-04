"""
Ce module rassemble les tâches pour interagir avec Moodle : création
de fichiers de groupes officiels de Cours/TD/TP où aléatoires
(binômes, trinômes par groupes) prêt à charger, descriptif de l'UV et
des intervenants sous forme de code HTML à copier-coller dans Moodle,
tableau des créneaux de l'UV sous forme de tableau HTML, création de
fichier Json pour copier-coller des restrictions d'accès en fonction
de l'appartenance à un groupe.
"""

import getpass
import json
import math
import os
import pprint
import random
import shlex
import sys
import textwrap

import mechanicalsoup
import numpy as np
import pandas as pd
import yapf.yapflib.yapf_api as yapf

from ..exceptions import GuvUserError
from ..logger import logger
from ..scripts.moodle_date import CondOr, CondProfil
from ..utils import (
    argument,
    generate_groupby,
    make_groups,
    normalize_string,
    pformat,
    sort_values,
)
from ..utils_config import Output, rel_to_dir
from .base import CliArgsMixin, SemesterTask, UVTask
from .evolutionary_algorithm import evolutionary_algorithm
from .internal import XlsStudentData

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"


class MoodleBrowser():
    def __init__(self):
        self.browser = mechanicalsoup.Browser(soup_config={'features': 'lxml'})
        self.is_authenticated = False

    def _authenticate(self):
        login_page = self.browser.get("https://moodle.utc.fr/login/index.php?authCAS=CAS")

        # Ask for the username
        username = input("Entrer votre login Moodle : ")

        # Safely ask for the password without showing it in the console
        password = getpass.getpass("Entrer votre mot de passe : ")

        login_form = mechanicalsoup.Form(login_page.soup.select_one("#fm1"))
        login_form.input({"username": username, "password": password})

        self.browser.submit(login_form, login_page.url)
        self.is_authenticated = True

    def get(self, url):
        if not self.is_authenticated:
            self._authenticate()
        return self.browser.get(url)


class CsvGroups(UVTask, CliArgsMixin):
    """Fichiers csv de groupes présents dans ``effectif.xlsx`` pour Moodle.

    L'option ``--groups`` permet de sélectionner les colonnes de groupes à
    exporter sous Moodle. Par défaut, les colonnes exportées sont les colonnes
    ``Cours``, ``TD`` et ``TP``.

    L'option ``--long`` permet d'exporter les noms de groupes de TD/TP au format
    long c'est à dire ``TP1`` et ``TD1`` au lieu de ``T1`` et ``D1``

    L'option ``--single`` permet de ne générer qu'un seul fichier.

    {options}

    Examples
    --------

    .. code:: bash

       guv csv_groups --groups Groupe_Projet

    """

    uptodate = False
    target_dir = "generated"
    target_name = "{ctype}_group_moodle.csv"

    cli_args = (
        argument(
            "-g",
            "--groups",
            metavar="COL,[COL,...]",
            type=lambda t: [s.strip() for s in t.split(",")],
            default="Cours,TD,TP",
            help="Liste des groupements à considérer via un nom de colonne. Par défaut, les groupements ``Cours``, ``TD`` et ``TP`` sont utilisés.",
        ),
        argument(
            "-l",
            "--long",
            action="store_true",
            help="Utiliser les noms de groupes de Cours/TD/TP au format long, c'est à dire \"TP1\" et \"TD1\" au lieu de \"T1\" et \"D1\""
        ),
        argument(
            "-s",
            "--single",
            action="store_true",
            help="Créer un unique fichier"
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
                        stu = row["Nom"] + " " + row["Prénom"]
                        logger.warning("Valeur non définie dans la colonne `%s` pour l'étudiant(e) %s", column_name, stu)

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

    Le nom des groupements est contrôlé par un modèle spécifié par
    l'argument ``-F`` (par défaut "D##_P1"). Les remplacements
    disponibles sont :

    - ## : remplacé par des nombres
    - @@ : remplacé par des lettres

    Le nom des groupes est contrôlé par un modèle spécifié par
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
        self.xls_merge = XlsStudentData.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target = self.build_target(group=normalize_string(self.group, type="file"))

    def run(self):
        df = XlsStudentData.read_target(self.xls_merge)

        self.check_if_present(
            df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
        )
        dff = df[["Adresse de courriel", self.group]]

        # Dictionary of group in GROUP and corresponding Cond
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
    """Création aléatoire de groupes d'étudiants prêt à charger sous Moodle.

    Cette tâche crée un fichier csv d'affectation des étudiants à un
    groupe directement chargeable sous Moodle. Si l'option
    ``--grouping`` est spécifiée les groupes sont créés à l'intérieur
    de chaque sous-groupe (de TP ou TD par exemple).

    Le nombre de groupes créés (au total ou par sous-groupes suivant
    ``--grouping``) est contrôlé par une des options mutuellement
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
            dest="_template",
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
            nargs="?",
            default=None,
            const=[],
            metavar="COL,...",
            type=lambda t: [s.strip() for s in t.split(",")],
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
            required=False,
            metavar="COL,[COL,...]",
            default=[],
            type=lambda t: [s.strip() for s in t.split(",")],
            help="Liste de colonnes de groupes déjà formés qui ne doivent plus être reformés."
        ),
        argument(
            "--affinity-groups",
            required=False,
            metavar="COL,[COL,...]",
            default=[],
            type=lambda t: [s.strip() for s in t.split(",")],
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

        self.xls_merge = XlsStudentData.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target = self.build_target(title=normalize_string(self.title, type="file"))

    def create_name_gen(self, tmpl):
        "Générateur de noms pour les groupes"

        if self.names is None:
            if "@" in tmpl and "#" in tmpl:
                raise self.parser.error(
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
                raise self.parser.error(
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
                raise FileNotFoundError(f"Le fichier de noms `{self.names[0]}` n'existe pas")
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

            logger.info("Pas de template spécifiée. La template par défaut est `%s`", self._template)

        return self._template

    def run(self):
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

        if "{grouping_name}" not in self.template and self.grouping is not None and not self.global_:
            raise self.parser.error("La template ne contient pas '{grouping_name}' mais l'option --grouping est active avec remise à zéro des noms de groupes")

        if self.ordered is not None and (self.affinity_groups or self.other_groups):
            raise self.parser.error("L'option ``ordered`` est incompatible avec les contraintes ``other-groups`` et ``affinity_groups``.")

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
            df = sort_values(df, ["Nom", "Prénom"])
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

        Ajouter les groupes au fichier `effectif.xlsx` avec le code suivant dans le fichier `config.py` de l'UV :

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
                print(f'{series.loc[index_i[0]]} : {first["Nom"]} {first["Prénom"]} -- {last["Nom"]} {last["Prénom"]} ({len(index_i)})')

        return series

    def add_names_to_grouping(self, partition, name, name_gen):
        """Give names to `groups`"""

        # Number of groups in partition
        num_groups = np.max(partition) + 1

        # Use generator to get templates
        try:
            templates = [next(name_gen) for _ in range(num_groups)]
        except StopIteration as e:
            raise GuvUserError("Les noms de groupes disponibles sont épuisés, utiliser # ou @ dans le modèle ou rajouter des noms dans `--names`.") from e

        names = np.array([pformat(tmpl, group_name=name) for tmpl in templates])
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
                logger.info(f"Partition optimale pour le groupe `{name}` trouvée en {num_variants} essais.")
            else:
                logger.info(f"Partition optimale trouvée en {num_variants} essais.")
        else:
            if name is not None:
                logger.warning(f"Pas de solution optimale trouvée pour le groupe `{name}` en {self.max_iter} essais, meilleure solution :")
            else:
                logger.warning(f"Pas de solution optimale trouvée en {self.max_iter} essais, meilleure solution :")

            best_coocurrence = get_coocurrence_matrix_from_array(best_partition)

            for column, weight_coocurrence in cooc_data["cooc_repulse_dict"].items():
                scores = weight_coocurrence * best_coocurrence
                n_errors = (np.sum(scores) - N) // 2
                if n_errors > 0:
                    logger.warning(f"- contrainte de non-appartenance par la colonne `{column}` violée {n_errors} fois :")

                    for i, j in np.column_stack(np.where(scores > 0)):
                        if i >= j:
                            continue

                        stu1 = " ".join(df[["Nom", "Prénom"]].iloc[i])
                        stu2 = " ".join(df[["Nom", "Prénom"]].iloc[j])
                        logger.warning(f"  - {stu1} -- {stu2}")
                else:
                    logger.warning(f"- contrainte de non-appartenance par la colonne `{column}` vérifiée")

            for column, weight_coocurrence in cooc_data["cooc_affinity_dict"].items():
                scores = (1 - weight_coocurrence) * best_coocurrence
                n_errors = np.sum(scores) // 2

                if n_errors > 0:
                    logger.warning(f"- contrainte d'affinité par la colonne `{column}` violée {n_errors} fois :")

                    for i, j in np.column_stack(np.where(scores > 0)):
                        if i >= j:
                            continue

                        stu1 = " ".join(df[["Nom", "Prénom"]].iloc[i])
                        stu2 = " ".join(df[["Nom", "Prénom"]].iloc[j])
                        logger.warning(f"  - {stu1} -- {stu2}")
                else:
                    logger.warning(f"- contrainte d'affinité par la colonne `{column}` vérifiée")

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


class FetchGroupId(SemesterTask, CliArgsMixin):
    """Crée un fichier de correspondance entre le nom et l'id des groupes Moodle.

    Pour utiliser certaines fonctionnalités de **guv** (notamment
    :class:`~guv.tasks.moodle.JsonRestriction` et
    :class:`~guv.tasks.moodle.JsonGroup`), il faut connaître la
    correspondance entre le nom des groupes et leur identifiant dans
    Moodle. Cette tâche permet de télécharger la correspondance en
    indiquant l'identifiant de l'UV/UE sous Moodle. Par exemple, l'id
    de l'url suivante :

        https://moodle.utc.fr/course/view.php?id=1718

    est 1718. La correspondance est téléchargée dans le sous-dossier
    ``document/`` du dossier du semestre. Il suffit ensuite de copier
    son contenu dans le fichier ``config.py`` de l'UV/UE
    correspondante.

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

    def groups(self, page):
        groups = {}
        for select in page.soup.find_all("select"):
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
        browser = MoodleBrowser()

        for id in self.ident_list:
            page = browser.get(self.url.format(id=id))
            groups = self.groups(page)

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
