"""
Fichier qui regroupe les tâches liées à la création de fiches de
présence.
"""

import os
import re
import zipfile
import tempfile
import pandas as pd
import latex

from doit.exceptions import TaskFailed

from .utils_config import Output
from .utils import (
    sort_values,
    check_columns,
    escape_tex,
    argument,
    pformat,
    LaTeXEnvironment,
)

from .tasks import UVTask, CliArgsMixin
from .dodo_students import XlsStudentDataMerge


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


class PdfAttendanceList(UVTask, CliArgsMixin):
    """Fichier pdf de feuilles de présence par groupes"""

    always_make = True
    target_dir = "generated"
    target_name = "attendance_{group}.zip"

    cli_args = (
        argument(
            "-g",
            "--group",
            help="Nom de la colonne du groupement à considérer",
        ),
        argument(
            "--save-tex",
            action="store_true",
            help="Met le(s) fichier(s) .tex généré(s) à disposition"
        )
    )

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.target = self.build_target()
        self.file_dep = [self.xls_merge]

    def run(self):
        df = pd.read_excel(self.xls_merge)

        if self.group:
            check_columns(df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR)

        template = "attendance_list.tex.jinja2"

        pdfs = []
        texs = []
        for gn, group in df.groupby(self.group or (lambda x: "all")):
            group = sort_values(group, ["Nom", "Prénom"])
            kwargs = {"group": f"Groupe: {escape_tex(gn)}", "filename": f"{gn}.pdf"}
            pdf, tex = pdf_attendance_list_render(group, template, **kwargs)
            pdfs.append(pdf)
            texs.append(tex)

        with Output(self.target) as target0:
            with zipfile.ZipFile(target0(), "w") as z:
                for filepath in pdfs:
                    z.write(filepath, os.path.basename(filepath))

        if self.save_tex:
            target = os.path.splitext(self.target)[0] + "_source.zip"
            with Output(target) as target0:
                with zipfile.ZipFile(target0(), "w") as z:
                    for filepath in texs:
                        z.write(filepath, os.path.basename(filepath))


class PdfAttendanceFull(UVTask, CliArgsMixin):
    """Fichier pdf de feuilles de présence par groupe et par séance"""

    always_make = True
    cli_args = (
        argument(
            "-g",
            "--group",
            required=True,
            help="Nom de la colonne du groupement à considérer",
        ),
        argument(
            "-n",
            "--slots",
            required=True,
            type=int,
            help="Nombre de colonne dans la feuille de présence",
        ),
        argument("-t", "--template", default="{group_name}{number}", help=""),
    )

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.target = self.build_target()
        self.kwargs = {**self.info, "nslot": self.slots, "ctype": self.group}

    def run(self):
        df = pd.read_excel(self.xls_merge)
        check_columns(
            df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
        )

        template = "attendance_name_full.tex.jinja2"
        pdfs = []

        context = {
            "slots_name": [
                escape_tex(pformat(self.template, group_name=self.group, number=i+1))
                for i in range(self.slots)
            ],
            **self.info,
            "nslot": self.slots,
            "ctype": escape_tex(self.group),
        }

        for gn, group in df.groupby(self.group):
            group = sort_values(group, ["Nom", "Prénom"])
            context["filename"] = gn + ".pdf"
            pdf, tex = pdf_attendance_list_render(group, template, group=escape_tex(gn), **context)
            pdfs.append(pdf)

        with Output(self.target) as target0:
            with zipfile.ZipFile(target0(), "w") as z:
                for filepath in pdfs:
                    z.write(filepath, os.path.basename(filepath))


class AttendanceSheetRoom(UVTask):
    """Feuille de présence par taille des salles"""

    always_make = True
    target_dir = "documents"
    target_name = "attendance_rooms.zip"

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.target = self.build_target()
        self.file_dep = [self.xls_merge]

    def rooms(self):
        groupby = {}
        while True:
            room = input("Salle: ")
            num = input("Nombre: ")
            if not room:
                if not num:
                    if groupby:
                        print("Liste des salles: \n%s" % groupby)
                        break
                    else:
                        raise Exception("Il faut au moins une salle")
            elif re.fullmatch("[0-9]+", num):
                groupby[room] = int(num)
        return groupby

    def run(self):
        groupby = self.rooms()

        def breaks(total, rooms):
            assert sum(rooms) >= total
            rest = sum(rooms) - total
            n = len(rooms)
            q = rest // n
            r = rest % n
            index = sorted(range(len(rooms)), key=lambda k: rooms[k])
            roomss = sorted(rooms)
            nrooms = [0] * n
            for i in range(n):
                eps = 1 if i + 1 <= r else 0
                nrooms[index[i]] = rooms[index[i]] - (q + eps)

            breaks = []
            nrooms0 = [0] + nrooms + [total - 1]
            curr = 0
            for i in range(len(nrooms0) - 2):
                breaks.append(
                    (curr + nrooms0[i], curr + nrooms0[i] + nrooms0[i + 1] - 1)
                )
                curr += nrooms0[i]

            return breaks

        df = pd.read_excel(self.xls_merge)
        if "Tiers-temps" in df.columns:
            df0 = df.loc[df["Tiers-temps"] == 0]
            dftt = df.loc[df["Tiers-temps"] != 0]
            if len(df.index) == 0:
                dftt = None
        else:
            df0 = df
            dftt = None

        total = len(df0.index)
        rooms_nums = [n for _, n in groupby.items()]
        rooms_name = [n for n, _ in groupby.items()]

        breaks = breaks(total, rooms_nums)
        pdfs = []
        for n, (i, j) in enumerate(breaks):
            stu1 = df0.iloc[i]["Nom"]
            stu2 = df0.iloc[j]["Nom"]
            filename = f"{rooms_name[n]}.pdf"
            pdf, tex = pdf_attendance_list_render(
                df0.iloc[i : (j + 1)], "attendance_list.tex.jinja2", filename=filename
            )
            pdfs.append(pdf)
            print(f"{stu1}--{stu2}")

        if dftt is not None:
            filename = "tiers-temps.pdf"
            pdf, tex = pdf_attendance_list_render(
                dftt, "attendance_list.tex.jinja2", filename=filename
            )
            pdfs.append(pdf)

        with Output(self.target) as target0:
            with zipfile.ZipFile(target0(), "w") as z:
                for filepath in pdfs:
                    z.write(filepath, os.path.basename(filepath))


class AttendanceSheet(UVTask, CliArgsMixin):
    """Fichiers pdf de feuilles de présence sans les noms des étudiants."""

    target_name = "{exam}_présence_%s.pdf"
    target_dir = "generated"
    unique_uv = True

    cli_args = (
        argument(
            "-e",
            "--exam",
            required=True,
            help="Nom de la colonne du groupement à considérer",
        ),
        argument(
            "-l",
            "--latex",
            action="store_true",
            help="Écrire le fichier LaTeX"
        )
    )

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.target = self.build_target()

    def run(self):
        groupby = {}
        while True:
            room = input("Salle: ")
            num = input("Nombre: ")
            if not room:
                if not num:
                    if groupby:
                        print("Liste des salles: \n%s" % groupby)
                        break
                    else:
                        return TaskFailed("Il faut au moins une salle")
            elif re.fullmatch("[0-9]+", num):
                groupby[room] = int(num)

        latex_env = LaTeXEnvironment()
        template = latex_env.get_template("attendance_list_noname.tex.jinja2")

        for room, number in groupby.items():
            tex = template.render(number=number, group=f"Salle {room}")

            target0 = self.target % room
            if self.latex:
                tex_filename = os.path.splitext(target0)[0] + '.tex'
                with Output(tex_filename) as target:
                    with open(target(), 'w') as fd:
                        fd.write(tex)

            pdf = latex.build_pdf(tex)
            with Output(target0) as target0:
                pdf.save_to(target0())
