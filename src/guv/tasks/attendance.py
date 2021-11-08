"""
Ce module rassemble les tâches liées à la création de fiches de
présence.
"""

import os
import zipfile
import tempfile
import shutil
import pandas as pd
import latex

from ..utils_config import Output
from ..utils import (
    sort_values,
    check_columns,
    argument,
    pformat,
    LaTeXEnvironment,
    make_groups
)

from .base import UVTask, CliArgsMixin
from .students import XlsStudentDataMerge


def pdf_attendance_list_render(df, tmpl_file, **kwargs):
    """Render LaTeX template and compile it."""

    latex_env = LaTeXEnvironment()
    template = latex_env.get_template(tmpl_file)

    df = sort_values(df, ["Nom", "Prénom"])
    students = [{"name": f'{row["Nom"]} {row["Prénom"]}'} for _, row in df.iterrows()]

    # Render template with provided data
    tex = template.render(students=students, **kwargs)

    temp_dir = tempfile.mkdtemp()

    filename = kwargs["filename"]
    pdf = latex.build_pdf(tex)
    filepath = os.path.join(temp_dir, filename)
    pdf.save_to(filepath)

    tex_filename = os.path.splitext(filename)[0] + '.tex'
    tex_filepath = os.path.join(temp_dir, tex_filename)
    with open(tex_filepath, "w") as fd:
        fd.write(tex)

    return filepath, tex_filepath


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

    always_make = True
    target_dir = "generated"
    target_name = "attendance_{group}"
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
        self.target = self.build_target(group=(self.group or "all"))
        latex_env = LaTeXEnvironment()
        self.template = latex_env.get_template(self.template_file)

    def pdf_attendance_render(self, **context):
        # Render template with context
        tex = self.template.render(**context)

        temp_dir = tempfile.mkdtemp()

        filename = context["filename"]
        pdf = latex.build_pdf(tex)
        filepath = os.path.join(temp_dir, filename)
        pdf.save_to(filepath)

        tex_filename = os.path.splitext(filename)[0] + '.tex'
        tex_filepath = os.path.join(temp_dir, tex_filename)
        with open(tex_filepath, "w") as fd:
            fd.write(tex)

        return filepath, tex_filepath

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
                    context["filename"] = f"{name}.pdf"
                    yield context
            else:
                df = pd.read_excel(self.xls_merge, engine="openpyxl")
                df = sort_values(df, ["Nom", "Prénom"])
                context["blank"] = False

                if self.tiers_temps:
                    check_columns(df, "Tiers-temps", file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR)
                    df_tt = df[df["Tiers-temps"] == 1]
                    df = df[df["Tiers-temps"] != 1]
                    context["group"] = "Tiers-temps"
                    context["filename"] = "Tiers_temps.pdf"
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
                    context["filename"] = f"{name}.pdf"
                    context["group"] = name
                    yield context

        else:
            df = pd.read_excel(self.xls_merge, engine="openpyxl")
            df = sort_values(df, ["Nom", "Prénom"])

            if self.tiers_temps:
                check_columns(df, "Tiers-temps", file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR)
                df_tt = df[df["Tiers-temps"] == 1]
                df = df[df["Tiers-temps"] != 1]
                context["group"] = "Tiers-temps"
                context["blank"] = self.blank
                context["num"] = len(df_tt)
                context["filename"] = "Tiers_temps.pdf"
                students = [{"name": f'{row["Nom"]} {row["Prénom"]}'} for _, row in df_tt.iterrows()]
                context["students"] = students
                yield context

            if self.group is not None:
                check_columns(df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR)

            for gn, group in df.groupby(self.group or (lambda x: "all")):
                if gn == "all":
                    gn = None
                context["group"] = gn
                context["blank"] = self.blank
                context["num"] = len(group)
                context["filename"] = f"{gn}.pdf"
                students = [{"name": f'{row["Nom"]} {row["Prénom"]}'} for _, row in group.iterrows()]
                context["students"] = students
                yield context

    def run(self):
        pdfs = []
        texs = []
        for context in self.generate_contexts():
            pdf, tex = self.pdf_attendance_render(**context)
            pdfs.append(pdf)
            texs.append(tex)

        # Écriture du pdf dans un zip si plusieurs
        if len(pdfs) == 1:
            with Output(self.target + ".pdf") as target0:
                shutil.move(pdfs[0], target0())
        else:
            with Output(self.target + ".zip") as target0:
                with zipfile.ZipFile(target0(), "w") as z:
                    for filepath in pdfs:
                        z.write(filepath, os.path.basename(filepath))

        # Écriture du tex dans un zip si plusieurs
        if self.save_tex:
            target = os.path.splitext(self.target)[0] + "_source.zip"
            with Output(target) as target0:
                if len(pdfs) == 1:
                    shutil.move(pdfs[0], target0())
                else:
                    with zipfile.ZipFile(target0(), "w") as z:
                        for filepath in texs:
                            z.write(filepath, os.path.basename(filepath))


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
    target_name = "attendance_{group}_full.zip"
    always_make = True
    cli_args = (
        argument(
            "-g",
            "--group",
            required=True,
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
            default="{group_name}{number}",
            help="Modèle permettant de fixer le nom des séances successives dans la feuille de présence. Par défaut on a ``{group_name}{number}``. Les seuls mots-clés supportés sont ``group_name`` et ``number``.",
        ),
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.parse_args()
        self.target = self.build_target()
        self.kwargs = {**self.info, "nslot": self.slots, "ctype": self.group}

    def run(self):
        df = pd.read_excel(self.xls_merge, engine="openpyxl")
        check_columns(
            df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
        )

        template = "attendance_name_full.tex.jinja2"
        pdfs = []

        base_context = {
            "slots_name": [
                pformat(self.template, group_name=self.group, number=i+1)
                for i in range(self.slots)
            ],
            **self.info,
            "nslot": self.slots,
            "ctype": self.group,
        }

        for gn, group in df.groupby(self.group):
            group = sort_values(group, ["Nom", "Prénom"])
            group_context = {
                "group": gn,
                "filename": f"{gn}.pdf"
            }
            context = {**base_context, **group_context}
            pdf, tex = pdf_attendance_list_render(group, template, **context)
            pdfs.append(pdf)

        with Output(self.target) as target0:
            with zipfile.ZipFile(target0(), "w") as z:
                for filepath in pdfs:
                    z.write(filepath, os.path.basename(filepath))
