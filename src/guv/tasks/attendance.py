"""
Ce module rassemble les tâches liées à la création de fiches de
présence.
"""

import pandas as pd

from ..utils import (LaTeXEnvironment, argument, make_groups, pformat,
                     sort_values)
from ..utils_config import ensure_present_columns, render_from_contexts
from .base import CliArgsMixin, UVTask
from .students import XlsStudentDataMerge


class PdfAttendance(UVTask, CliArgsMixin):
    """Fichier pdf de feuilles de présence.

    Cette tâche génère un fichier pdf ou un fichier zip de fichiers
    pdf contenant des feuilles de présence.

    {options}

    Examples
    --------

    - Feuille de présence nominative :

      .. code:: bash

         guv pdf_attendance --title "Examen"

    - Feuilles de présence nominative par groupe de TP :

      .. code:: bash

         guv pdf_attendance --title "Examen de TP" --group TP

    - Feuilles de présence sans les noms par groupe de TP :

      .. code:: bash

         guv pdf_attendance --title "Examen de TP" --group TP --blank

    - Feuilles de présence nominative découpées pour trois salles :

      .. code:: bash

         guv pdf_attendance --title "Examen de TP" --count 24 24 24 --name \"Salle 1\" \"Salle 2\" \"Salle 3\"

    """

    uptodate = True
    target_dir = "generated"
    target_name = "{title}_{group}"
    template_file = "attendance.tex.jinja2"

    cli_args = (
        argument(
            "-t",
            "--title",
            default="Feuille de présence",
            help="Spécifie un titre qui sera utilisé dans les feuilles de présence."
        ),
        argument(
            "-g",
            "--group",
            help="Permet de créer des groupes pour faire autant de feuilles de présence. Il faut spécifier une colonne du fichier central ``effectif.xlsx``.",
        ),
        argument(
            "-b",
            "--blank",
            action="store_true",
            default=False,
            help="Ne pas faire apparaitre le nom des étudiants (utile seulement avec --group)."
        ),
        argument(
            "-c",
            "--count",
            type=int,
            nargs="*",
            help="Utilise une liste d'effectifs au lieu de ``--group``. Le nom des groupes peut être spécifié par ``--names``. Sinon, les noms de groupe sont de la forme ``Groupe 1``, ``Groupe 2``,..."
        ),
        argument(
            "-n",
            "--names",
            nargs="*",
            help="Spécifie le nom des groupes correspondants à ``--count``. La liste doit être de même taille que ``--count``."
        ),
        argument(
            "-e",
            "--extra",
            type=int,
            default=0,
            help="Permet de rajouter des lignes supplémentaires vides en plus de celles déjà présentes induites par ``--group`` ou fixées par ``--count``."
        ),
        argument(
            "--tiers-temps",
            action="store_true",
            default=False,
            help="Permet de dédier une feuille de présence spécifique pour les étudiants marqués comme tiers-temps dans le fichier central ``effectifs.xlsx``."
        ),
        argument(
            "--save-tex",
            action="store_true",
            default=False,
            help="Permet de laisser les fichiers .tex générés pour modification éventuelle."
        )
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target = self.build_target(
            group=(self.group or "all"),
            title=self.title.replace(" ", "_")
        )
        latex_env = LaTeXEnvironment()
        self.template = latex_env.get_template(self.template_file)

    def generate_contexts(self):
        "Generate contexts to pass to Jinja2 templates."

        if self.group and (self.count or self.names):
            raise Exception("Les options --group et --count ou --names sont incompatibles")

        context = {
            "title": self.title,
            "extra": self.extra,
            **self.info
        }

        if self.count:
            if self.names:
                if len(self.count) != len(self.names):
                    raise Exception("Les options --count et --names doivent être de même longueur")
            else:
                self.names = [f"Groupe_{i+1}" for i in range(len(self.count))]

            if self.blank:
                context["blank"] = True
                for num, name in zip(self.count, self.names):
                    context["group"] = name
                    context["num"] = num
                    context["filename_no_ext"] = f"{name}"
                    yield context
            else:
                df = pd.read_excel(self.xls_merge, engine="openpyxl")
                df = sort_values(df, ["Nom", "Prénom"])
                context["blank"] = False

                if self.tiers_temps:
                    ensure_present_columns(
                        df, "Tiers-temps", file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
                    )
                    df_tt = df[df["Tiers-temps"] == "Oui"]
                    df = df[df["Tiers-temps"] != "Oui"]
                    context["group"] = "Tiers-temps"
                    context["filename_no_ext"] = "Tiers_temps"
                    students = [{"name": f'{row["Nom"]} {row["Prénom"]}'} for _, row in df_tt.iterrows()]
                    context["students"] = students
                    yield context

                if sum(self.count) < len(df.index):
                    raise Exception("Les effectifs cumulés ne suffisent pas")

                groups = make_groups(df.index, self.count)
                for name, idxs in zip(self.names, groups):
                    group = df.loc[idxs]
                    print(name, ":", " ".join(group.iloc[0][["Nom", "Prénom"]]), "--",
                          " ".join(group.iloc[-1][["Nom", "Prénom"]]))
                    students = [{"name": f'{row["Nom"]} {row["Prénom"]}'} for _, row in group.iterrows()]
                    context["students"] = students
                    context["filename_no_ext"] = f"{name}"
                    context["group"] = name
                    yield context

        else:
            df = pd.read_excel(self.xls_merge, engine="openpyxl")
            df = sort_values(df, ["Nom", "Prénom"])

            if self.tiers_temps:
                ensure_present_columns(
                    df, "Tiers-temps", file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
                )
                df_tt = df[df["Tiers-temps"] == 1]
                df = df[df["Tiers-temps"] != 1]
                context["group"] = "Tiers-temps"
                context["blank"] = self.blank
                context["num"] = len(df_tt)
                context["filename_no_ext"] = "Tiers_temps"
                students = [{"name": f'{row["Nom"]} {row["Prénom"]}'} for _, row in df_tt.iterrows()]
                context["students"] = students
                yield context

            if self.group is not None:
                ensure_present_columns(
                    df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
                )

            for gn, group in df.groupby(self.group or (lambda x: "all")):
                if gn == "all":
                    gn = None
                context["group"] = gn
                context["blank"] = self.blank
                context["num"] = len(group)
                context["filename_no_ext"] = f"{gn}"
                students = [{"name": f'{row["Nom"]} {row["Prénom"]}'} for _, row in group.iterrows()]
                context["students"] = students
                yield context

    def run(self):
        contexts = self.generate_contexts()

        render_from_contexts(
            self.template, contexts, save_tex=self.save_tex, target=self.target
        )


class PdfAttendanceFull(UVTask, CliArgsMixin):
    """Fichier zip de feuilles de présence nominatives par groupe et par semestre.

    Permet d'avoir un seule feuille de présence pour tout le semestre.

    {options}

    Examples
    --------

    .. code:: bash

       guv pdf_attendance_full --group TP --template "G{group_name}_{number}"

    """

    target_dir = "generated"
    target_name = "{title}_{group}_full"
    template_file = "attendance_name_full.tex.jinja2"
    uptodate = True
    cli_args = (
        argument(
            "--title",
            default="Feuille de présence",
            help="Spécifie un titre qui sera utilisé dans les feuilles de présence."
        ),
        argument(
            "-g",
            "--group",
            help="Permet de spécifier une colonne de groupes pour faire des feuilles de présence par groupes.",
        ),
        argument(
            "-n",
            "--slots",
            required=True,
            type=int,
            help="Permet de spécifier le nombre de séances pour le semestre c'est à dire le nombre de colonne dans la feuille de présence.",
        ),
        argument(
            "-t",
            "--template",
            help="Modèle permettant de fixer le nom des séances successives dans la feuille de présence. Par défaut on a ``S{number}``. Le seul mot-clé supporté est ``number``.",
        ),
        argument(
            "--save-tex",
            action="store_true",
            default=False,
            help="Permet de laisser les fichiers .tex générés pour modification éventuelle."
        )
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.parse_args()
        self.target = self.build_target(title=self.title.replace(" ", "_"), group=self.group or "all")

    def run(self):
        df = pd.read_excel(self.xls_merge, engine="openpyxl")
        if self.group is not None:
            ensure_present_columns(
                df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
            )

        if self.template is None:
            self.template = "S{number}"

        if self.group is None and "{group_name}" in self.template:
            raise Exception("Pas de groupe mais `{group_name}` présent dans le modèle")

        contexts = self.generate_contexts(df)

        render_from_contexts(
            self.template_file, contexts, save_tex=self.save_tex, target=self.target
        )

    def generate_contexts(self, df):
        base_context = {
            "slots_name": [
                pformat(self.template, number=i+1)
                for i in range(self.slots)
            ],
            **self.info,
            "nslot": self.slots,
            "title": self.title
        }

        key = (lambda x: "all") if self.group is None else self.group

        for gn, group in df.groupby(key):
            group = sort_values(group, ["Nom", "Prénom"])
            students = [
                {"name": f'{row["Nom"]} {row["Prénom"]}'} for _, row in group.iterrows()
            ]
            group_context = {
                "group": None if gn == "all" else gn,
                "filename_no_ext": gn,
                "students": students,
            }
            yield {**base_context, **group_context}
