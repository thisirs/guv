"""
Fichier qui regroupe les tâches liées à la création de fiches de
présence.
"""

import os
import re
import zipfile
import tempfile
import pandas as pd
import jinja2
import latex

from doit.exceptions import TaskFailed

from .config import settings
from .utils_config import Output, generated
from .utils import sort_values, check_columns, escape_tex, argument

from .tasks import UVTask, CliArgsMixin
from .dodo_students import XlsStudentDataMerge


def pdf_attendance_list_render(df, template, **kwargs):
    """Render LaTeX template and compile it."""

    jinja_dir = os.path.join(os.path.dirname(__file__), "templates")
    latex_jinja_env = jinja2.Environment(
        block_start_string="((*",
        block_end_string="*))",
        variable_start_string="(((",
        variable_end_string=")))",
        comment_start_string="((=",
        comment_end_string="=))",
        loader=jinja2.FileSystemLoader(jinja_dir),
    )
    template = latex_jinja_env.get_template(template)

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


class TaskPdfAttendanceList(UVTask, CliArgsMixin):
    """Fichier pdf de fiches de présence"""

    always_make = True

    cli_args = (
        argument(
            "-g",
            "--group",
            required=True,
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
        self.xls_merge = generated(XlsStudentDataMerge.target, **self.info)
        self.target = generated(f"attendance_{self.group}.zip", **self.info)
        self.file_dep = [self.xls_merge]

    def run(self):
        df = pd.read_excel(self.xls_merge, engine="openpyxl")

        if self.group == "all":
            self.group = None
        else:
            check_columns(df, self.group, file=self.xls_merge, base_dir=settings.BASE_DIR)

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
    """Feuilles de présence pour toutes les séances"""

    always_make = True
    cli_args = (
        argument(
            "-c",
            "--course",
            required=True,
            help="Nom de la colonne du groupement à considérer",
        ),
        argument(
            "-n",
            "--slots",
            type=int,
            default=14,
            help="Nombre de colonne dans la feuille de présence",
        ),
    )

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.xls_merge = generated(XlsStudentDataMerge.target, **self.info)
        self.target = generated(f"attendance_{self.course}_full.zip", **self.info)
        self.kwargs = {**self.info, "nslot": self.slots, "ctype": self.course}

    def run(self):
        df = pd.read_excel(self.xls_merge, engine="openpyxl")
        template = "attendance_name_full.tex.jinja2"
        pdfs = []
        ctype = self.kwargs["ctype"]

        check_columns(df, ctype, file=self.xls_merge, base_dir=settings.BASE_DIR)
        for gn, group in df.groupby(ctype):
            group = sort_values(group, ["Nom", "Prénom"])
            self.kwargs["filename"] = gn + ".pdf"
            pdf, tex = pdf_attendance_list_render(group, template, group=gn, **self.kwargs)
            pdfs.append(pdf)

        with Output(self.target) as target0:
            with zipfile.ZipFile(target0(), "w") as z:
                for filepath in pdfs:
                    z.write(filepath, os.path.basename(filepath))


class AttendanceSheetRoom(UVTask):
    """Feuille de présence par taille des salles"""

    always_make = True
    target = "attendance_rooms.zip"

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.xls_merge = generated(XlsStudentDataMerge.target, **info)
        self.file_dep = [self.xls_merge]
        self.target = generated(AttendanceSheetRoom.target, **info)

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

        df = pd.read_excel(self.xls_merge, engine="openpyxl")
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

    cli_args = (
        argument(
            "-e",
            "--exam",
            required=True,
            help="Nom de la colonne du groupement à considérer",
        ),
    )

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.target = generated(f"{self.exam}_présence_%s.pdf", **info)

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

        jinja_dir = os.path.join(os.path.dirname(__file__), "templates")
        latex_jinja_env = jinja2.Environment(
            block_start_string="((*",
            block_end_string="*))",
            variable_start_string="(((",
            variable_end_string=")))",
            comment_start_string="((=",
            comment_end_string="=))",
            loader=jinja2.FileSystemLoader(jinja_dir),
        )

        template = latex_jinja_env.get_template("attendance_list_noname.tex.jinja2")

        for room, number in groupby.items():
            tex = template.render(number=number, group=f"Salle {room}")

            target0 = self.target % room
            # with open(target0+'.tex', 'w') as fd:
            #     fd.write(tex)

            pdf = latex.build_pdf(tex)
            pdf.save_to(target0)
