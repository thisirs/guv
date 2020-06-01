import os
import re
import zipfile
import tempfile
import pandas as pd
import jinja2
import latex

from doit.exceptions import TaskFailed

from .utils import (
    Output,
    generated,
    argument,
    parse_args,
    get_unique_uv,
    actionfailed_on_exception,
    taskfailed_on_exception,
    check_columns,
)

from .dodo_students import task_xls_student_data_merge


def pdf_attendance_list_render(df, template, **kwargs):
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

    temp_dir = tempfile.mkdtemp()
    df = df.sort_values(["Nom", "Prénom"])
    students = [{"name": f'{row["Nom"]} {row["Prénom"]}'} for _, row in df.iterrows()]
    tex = template.render(students=students, **kwargs)
    pdf = latex.build_pdf(tex)
    filename = kwargs["filename"]
    filepath = os.path.join(temp_dir, filename)
    pdf.save_to(filepath)
    return filepath


@actionfailed_on_exception
def task_pdf_attendance_list():
    """Fichier pdf de fiches de présence"""

    @taskfailed_on_exception
    def pdf_attendance_list(xls_merge, group, target):
        df = pd.read_excel(xls_merge)

        if group == "all":
            group = None
        else:
            check_columns(df, group, file=xls_merge)

        template = "attendance_list.tex.jinja2"

        pdfs = []
        for gn, group in df.groupby(group or (lambda x: "all")):
            group = group.sort_values(["Nom", "Prénom"])
            kwargs = {"group": f"Groupe: {gn}", "filename": f"{gn}.pdf"}
            pdf = pdf_attendance_list_render(group, template, **kwargs)
            pdfs.append(pdf)

        with Output(target) as target0:
            with zipfile.ZipFile(target0(), "w") as z:
                for filepath in pdfs:
                    z.write(filepath, os.path.basename(filepath))

    args = parse_args(
        task_pdf_attendance_list,
        argument(
            "-g",
            "--group",
            required=True,
            help="Nom de la colonne du groupement à considérer",
        ),
    )

    planning, uv, info = get_unique_uv()
    xls_merge = generated(task_xls_student_data_merge.target, **info)
    target = generated(f"attendance_{args.group}.zip", **info)

    return {
        "file_dep": [xls_merge],
        "targets": [target],
        "actions": [(pdf_attendance_list, [xls_merge, args.group, target])],
    }


def pdf_attendance_full_render(df, template, **kwargs):
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

    temp_dir = tempfile.mkdtemp()
    df = df.sort_values(["Nom", "Prénom"])
    students = [{"name": f'{row["Nom"]} {row["Prénom"]}'} for _, row in df.iterrows()]
    tex = template.render(students=students, **kwargs)
    pdf = latex.build_pdf(tex)
    filename = kwargs["group"] + ".pdf"
    filepath = os.path.join(temp_dir, filename)
    pdf.save_to(filepath)
    return filepath


@actionfailed_on_exception
def task_pdf_attendance_full():
    """Feuilles de présence pour toutes les séances"""

    @taskfailed_on_exception
    def pdf_attendance_full(xls_merge, target, **kwargs):
        df = pd.read_excel(xls_merge)
        template = "attendance_name_full.tex.jinja2"
        pdfs = []
        ctype = kwargs["ctype"]

        check_columns(df, ctype, file=xls_merge)
        for gn, group in df.groupby(ctype):
            group = group.sort_values(["Nom", "Prénom"])
            pdf = pdf_attendance_full_render(group, template, group=gn, **kwargs)
            pdfs.append(pdf)

        with Output(target) as target0:
            with zipfile.ZipFile(target0(), "w") as z:
                for filepath in pdfs:
                    z.write(filepath, os.path.basename(filepath))

    args = parse_args(
        task_pdf_attendance_full,
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

    planning, uv, info = get_unique_uv()
    xls_merge = generated(task_xls_student_data_merge.target, **info)
    target = generated(f"attendance_{args.course}_full.zip", **info)
    kwargs = {**info, "nslot": args.slots, "ctype": args.course}
    return {
        "file_dep": [xls_merge],
        "targets": [target],
        "actions": [(pdf_attendance_full, [xls_merge, target], kwargs)],
        "uptodate": [False],
    }


@actionfailed_on_exception
def task_attendance_sheet_room():
    """Feuille de présence par taille des salles"""

    def attendance_sheet_room(csv, target):
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

        df = pd.read_excel(xls_merge)
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
            pdf = pdf_attendance_list_render(
                df0.iloc[i : (j + 1)], "attendance_list.tex.jinja2", filename=filename
            )
            pdfs.append(pdf)
            print(f"{stu1}--{stu2}")

        if dftt is not None:
            filename = "tiers-temps.pdf"
            pdf = pdf_attendance_list_render(
                dftt, "attendance_list.tex.jinja2", filename=filename
            )
            pdfs.append(pdf)

        with Output(target) as target0:
            with zipfile.ZipFile(target0(), "w") as z:
                for filepath in pdfs:
                    z.write(filepath, os.path.basename(filepath))

    planning, uv, info = get_unique_uv()
    xls_merge = generated(task_xls_student_data_merge.target, **info)
    target = generated(f"attendance_rooms.zip", **info)
    return {
        "file_dep": [xls_merge],
        "targets": [target],
        "actions": [(attendance_sheet_room, [xls_merge, target])],
    }


@actionfailed_on_exception
def task_attendance_sheet():
    """Fichiers pdf de feuilles de présence sans les noms des étudiants."""

    def generate_attendance_sheets(target, **kwargs):
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

            target0 = target % room
            # with open(target0+'.tex', 'w') as fd:
            #     fd.write(tex)

            pdf = latex.build_pdf(tex)
            pdf.save_to(target0)

    args = parse_args(
        task_attendance_sheet,
        argument(
            "-e",
            "--exam",
            required=True,
            help="Nom de la colonne du groupement à considérer",
        ),
    )

    planning, uv, info = get_unique_uv()
    target = generated(f"{args.exam}_présence_%s.pdf", **info)

    return {
        "targets": [target],
        "actions": [(generate_attendance_sheets, [target])],
    }
