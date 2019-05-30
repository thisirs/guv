import os
import re
import math
import random
import hashlib
import shutil
import glob
import zipfile
import tempfile
import asyncio
import aiohttp
import numpy as np
import pandas as pd
import jinja2
import latex
from openpyxl import Workbook
from openpyxl import utils
from openpyxl.utils.dataframe import dataframe_to_rows

from doit.exceptions import TaskFailed

from .config import settings
from .utils import (
    Output,
    add_templates,
    documents,
    generated,
    selected_uv,
    action_msg,
    escape_tex,
    argument,
    parse_args,
    get_unique_uv,
    actionfailed_on_exception,
    taskfailed_on_exception,
    check_columns,
    URL,
)
from .scripts.parse_utc_list import parse_UTC_listing
from .scripts.add_student_data import (
    add_moodle_data,
    add_UTC_data,
    add_tiers_temps,
    add_switches,
)


@add_templates(target="inscrits.raw")
def task_inscrits():
    def inscrits(doc):
        if not os.path.exists(doc):
            return TaskFailed(f"Pas de fichier `{doc}'")
        else:
            print(f"Utilisation du fichier `{doc}'")

    for planning, uv, info in selected_uv():
        doc = documents(task_inscrits.target, **info)
        yield {
            "name": f"{planning}_{uv}",
            "actions": [(inscrits, [doc])],
            "targets": [doc],
            "uptodate": [True],
        }


@add_templates(target="inscrits.csv")
def task_csv_inscrits():
    """Construit un fichier CSV à partir des données brutes de la promo
    fournies par l'UTC."""

    def csv_inscrits(fn, target):
        df = parse_UTC_listing(fn)
        with Output(target) as target:
            df.to_csv(target(), index=False)

    for planning, uv, info in selected_uv():
        utc_listing = documents(task_inscrits.target, **info)
        target = generated(task_csv_inscrits.target, **info)
        yield {
            "name": f"{planning}_{uv}",
            "file_dep": [utc_listing],
            "targets": [target],
            "actions": [(csv_inscrits, [utc_listing, target])],
            "verbosity": 2,
        }


@add_templates(target="student_data.xlsx")
def task_xls_student_data():
    """Fusionne les informations sur les étudiants fournies par Moodle et
l'UTC."""

    def merge_student_data(target, **kw):
        if "extraction_ENT" in kw:
            df = pd.read_excel(kw["extraction_ENT"])
            # Split information in 2 columns
            df[["Branche", "Semestre"]] = df.pop('Spécialité 1').str.extract(
                '(?P<Branche>[a-zA-Z]+) *(?P<Semestre>[0-9]+)',
                expand=True
            )

            if "csv_moodle" in kw:
                df = add_moodle_data(df, kw["csv_moodle"])

            if "csv_UTC" in kw:
                df = add_UTC_data(df, kw["csv_UTC"])
        elif "csv_UTC" in kw:
            df = pd.read_csv(kw["csv_UTC"])
            if "csv_moodle" in kw:
                df = add_moodle_data(df, kw["csv_moodle"])
        elif "csv_moodle" in kw:
            df = pd.read_csv(kw["csv_moodle"])

        if "tiers_temps" in kw:
            df = add_tiers_temps(df, kw["tiers_temps"])

        if "TD_switches" in kw:
            df = add_switches(df, kw["TD_switches"], "TD")

        if "TP_switches" in kw:
            df = add_switches(df, kw["TP_switches"], "TP")

        dff = df.sort_values(["Nom", "Prénom"])

        with Output(target) as target:
            dff.to_excel(target(), index=False)

    for planning, uv, info in selected_uv():
        kw = {}
        deps = []

        extraction_ENT = documents("extraction_enseig_note.xlsx", **info)
        if os.path.exists(extraction_ENT):
            kw["extraction_ENT"] = extraction_ENT
            deps.append(extraction_ENT)

        csv_moodle = documents("inscrits_moodle.csv", **info)
        if os.path.exists(csv_moodle):
            kw["csv_moodle"] = csv_moodle
            deps.append(csv_moodle)

        csv_UTC = generated(task_csv_inscrits.target, **info)
        raw_UTC = documents(task_inscrits.target, **info)
        if os.path.exists(raw_UTC):
            kw["csv_UTC"] = csv_UTC
            deps.append(csv_UTC)

        tiers_temps = documents("tiers_temps.raw", **info)
        if os.path.exists(tiers_temps):
            kw["tiers_temps"] = tiers_temps
            deps.append(tiers_temps)

        TD_switches = documents("TD_switches.raw", **info)
        if os.path.exists(TD_switches):
            kw["TD_switches"] = TD_switches
            deps.append(TD_switches)

        TP_switches = documents("TP_switches.raw", **info)
        if os.path.exists(TP_switches):
            kw["TP_switches"] = TP_switches
            deps.append(TP_switches)

        target = generated(task_xls_student_data.target, **info)

        if deps:
            yield {
                "name": f"{planning}_{uv}",
                "file_dep": deps,
                "targets": [target],
                "actions": [(merge_student_data, [target], kw)],
                "verbosity": 2,
            }
        else:
            yield action_msg("Pas de données étudiants", name=f"{planning}_{uv}")


@add_templates(target="student_data_merge.xlsx")
def task_xls_student_data_merge():
    """Ajoute toutes les autres informations étudiants"""

    def merge_student_data(source, target, data):
        df = pd.read_excel(source)

        for path, aggregater in data.items():
            print("Aggregating %s" % path)
            df = aggregater(df, path)

        dff = df.sort_values(["Nom", "Prénom"])

        wb = Workbook()
        ws = wb.active

        for r in dataframe_to_rows(dff, index=False, header=True):
            ws.append(r)

        for cell in ws[1]:
            cell.style = 'Pandas'

        max_column = ws.max_column
        max_row = ws.max_row
        ws.auto_filter.ref = 'A1:{}{}'.format(
            utils.get_column_letter(max_column),
            max_row)

        with Output(target) as target0:
            wb.save(target0())

        target = os.path.splitext(target)[0] + ".csv"
        with Output(target) as target:
            dff.to_csv(target(), index=False)

    for planning, uv, info in selected_uv():
        source = generated(task_xls_student_data.target, **info)
        target = generated(task_xls_student_data_merge.target, **info)
        deps = [source]
        data_exist = {}

        for path, aggregater in settings.AGGREGATE_DOCUMENTS.items():
            if os.path.exists(path):
                deps.append(path)
                data_exist[path] = aggregater

        yield {
            "name": f"{planning}_{uv}",
            "file_dep": deps,
            "targets": [target],
            "actions": [(merge_student_data, [source, target, data_exist])],
            "verbosity": 2,
        }


def task_csv_exam_groups():
    """Fichier csv des demi-groupe de TP pour le passage des examens de TP."""

    @taskfailed_on_exception
    def csv_exam_groups(target, target_moodle, xls_merge):
        df = pd.read_excel(xls_merge)

        def exam_split(df):
            if "Tiers-temps" in df.columns:
                dff = df.sort_values("Tiers-temps", ascending=False)
            else:
                dff = df
            n = len(df.index)
            m = math.ceil(n / 2)
            sg1 = dff.iloc[:m, :]["TP"] + "i"
            sg2 = dff.iloc[m:, :]["TP"] + "ii"
            dff["TPE"] = pd.concat([sg1, sg2])
            return dff

        check_columns(df, "TP", file=xls_merge)

        dff = df.groupby("TP", group_keys=False).apply(exam_split)
        dff = dff[["Adresse de courriel", "TPE"]]

        with Output(target) as target0:
            dff.to_csv(target0(), index=False)

        with Output(target_moodle) as target:
            dff.to_csv(target(), index=False, header=False)

    for planning, uv, info in selected_uv():
        deps = [generated(task_xls_student_data_merge.target, **info)]
        target = generated("exam_groups.csv", **info)
        target_moodle = generated("exam_groups_moodle.csv", **info)

        yield {
            "name": f"{planning}_{uv}",
            "actions": [(csv_exam_groups, [target, target_moodle, deps[0]])],
            "file_dep": deps,
            "targets": [target_moodle],
            "verbosity": 2,
        }


def task_csv_groups():
    """Fichiers csv des groupes de Cours/TD/TP pour Moodle"""

    @taskfailed_on_exception
    def csv_groups(target, xls_merge, ctype):
        df = pd.read_excel(xls_merge)

        check_columns(df, ctype, file=xls_merge)
        dff = df[["Courriel", ctype]]

        with Output(target) as target:
            dff.to_csv(target(), index=False, header=False)

    for planning, uv, info in selected_uv():
        deps = [generated(task_xls_student_data_merge.target, **info)]

        for ctype in ["Cours", "TD", "TP"]:
            target = generated(f"{ctype}_group_moodle.csv", **info)

            yield {
                "name": f"{planning}_{uv}_{ctype}",
                "actions": [(csv_groups, [target, deps[0], ctype])],
                "file_dep": deps,
                "targets": [target],
                "verbosity": 2,
            }


@actionfailed_on_exception
def task_csv_binomes():
    """Fichier csv des groupes + binômes"""

    def csv_binomes(target, target_moodle, xls_merge, ctype, project, other_groups):
        df = pd.read_excel(xls_merge)

        def binome_match(row1, row2, other_groups=None, foreign=True):
            "Renvoie vrai si le binôme est bon"

            if foreign:
                e = [
                    "DIPLOME ETAB ETRANGER SECONDAIRE",
                    "DIPLOME ETAB ETRANGER SUPERIEUR",
                    "AUTRE DIPLOME UNIVERSITAIRE DE 1ER CYCLE HORS DUT",
                ]

                # 2 étrangers == catastrophe
                if (
                    row1["Dernier diplôme obtenu"] in e
                    and row2["Dernier diplôme obtenu"] in e
                ):
                    return False

                # 2 GB == catastrophe
                if row1["Branche"] == 'GB' and row2["Branche"] == 'GB':
                    return False

            # Binomes précédents
            if other_groups is not None:
                for gp in other_groups:
                    if row1[gp] == row2[gp]:
                        return False

            return True

        def trinome_match(row1, row2, row3, other_groups=None):
            a = binome_match(row1, row2, other_groups=other_groups, foreign=False)
            b = binome_match(row1, row3, other_groups=other_groups, foreign=False)
            c = binome_match(row2, row3, other_groups=other_groups, foreign=False)
            return a or b or c

        class Ooops(Exception):
            pass

        def add_binome(group, other_groups=None, foreign=True):
            gpn = group.name

            while True:
                try:
                    # Création de GROUPS qui associe indice avec groupe
                    index = list(group.index)
                    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")[::-1]
                    l = letters[0]
                    groups = {}
                    maxiter = 1000
                    it = 0
                    while index:
                        it += 1
                        if it > maxiter:
                            raise Ooops
                        if len(index) == 4:
                            stu1, stu2, stu3, stu4 = random.sample(index, 4)
                            if not binome_match(
                                group.loc[stu1], group.loc[stu2]
                            ) or not binome_match(group.loc[stu3], group.loc[stu4]):
                                raise Ooops
                            l = letters.pop()
                            groups[stu1] = l
                            groups[stu2] = l
                            l = letters.pop()
                            groups[stu3] = l
                            groups[stu4] = l
                            index.remove(stu1)
                            index.remove(stu2)
                            index.remove(stu3)
                            index.remove(stu4)
                        elif len(index) == 2:
                            stu1, stu2 = random.sample(index, 2)
                            if not binome_match(group.loc[stu1], group.loc[stu2]):
                                raise Ooops
                            l = letters.pop()
                            groups[stu1] = l
                            groups[stu2] = l
                            index.remove(stu1)
                            index.remove(stu2)

                        # if len(index) == 1:
                        #     # Le binome du dernier groupe
                        #     stu1, stu2 = [k for k, v in groups.items() if v == l]
                        #     if trinome_match(group.loc[stu1], group.loc[stu2], group.loc[index[0]], other_groups=other_groups):
                        #         raise Ooops
                        #     groups[index[0]] = l
                        #     index = []
                        else:
                            stu1, stu2, stu3 = random.sample(index, 3)
                            if not trinome_match(
                                group.loc[stu1],
                                group.loc[stu2],
                                group.loc[stu3],
                                other_groups=other_groups,
                            ):
                                raise Ooops
                            l = letters.pop()
                            groups[stu1] = l
                            groups[stu2] = l
                            groups[stu3] = l
                            index.remove(stu1)
                            index.remove(stu2)
                            index.remove(stu3)
                    # do stuff
                except Ooops:
                    continue
                break

            def add_group(g):
                g["binome"] = f"{gpn}_{project}_{g.name}"
                return g

            gb = group.groupby(pd.Series(groups)).apply(add_group)

            return gb

        check_columns(df, ctype, file=xls_merge)

        gdf = df.groupby(ctype)

        if other_groups is not None:
            if not isinstance(other_groups, list):
                other_groups = [other_groups]

            diff = set(other_groups) - set(df.columns.values)
            if diff:
                s = "s" if len(diff) > 1 else ""
                return TaskFailed(
                    f"Colonne{s} inconnue{s} : `{', '.join(diff)}'; les colonnes sont : {', '.join(df.columns)}"
                )

        df = gdf.apply(add_binome, other_groups=other_groups)
        df = df[["Courriel", ctype, "binome"]]

        # dfa = df[['Adresse de courriel', ctype]].rename(columns={ctype: 'group'})
        dfb = df[["Courriel", "binome"]].rename(columns={"binome": "group"})
        # df = pd.concat([dfa, dfb])
        df = dfb
        df = df.sort_values("group")

        with Output(target) as target0:
            df.to_csv(target0(), index=False)

        with Output(target_moodle) as target:
            df.to_csv(target(), index=False, header=False)

    args = parse_args(
        task_csv_binomes,
        argument('-c', '--course', required=True),
        argument('-p', '--project', required=True),
        argument('-o', '--other_group', required=False, default=None),
    )

    planning, uv, info = get_unique_uv()
    xls_merge = generated(task_xls_student_data_merge.target, **info)
    target = generated(f"{args.course}_{args.project}_binomes.csv", **info)
    target_moodle = generated(f"{args.course}_{args.project}_binomes_moodle.csv", **info)
    deps = [xls_merge]

    return {
        "actions": [
            (
                csv_binomes,
                [target, target_moodle, xls_merge, args.course, args.project, args.other_group],
            )
        ],
        "file_dep": deps,
        "targets": [target_moodle],  # target_moodle only to
        # avoid circular dep
    }


@actionfailed_on_exception
def task_pdf_trombinoscope():
    """Fichier PDF des trombinoscopes par groupes et/ou sous-groupes"""

    @taskfailed_on_exception
    def pdf_trombinoscope(xls_merge, target, groupby, subgroupby, width):
        async def download_image(session, login):
            url = URL + login
            async with session.get(url) as response:
                content = await response.content.read()
                if len(content) < 100:
                    shutil.copyfile(
                        os.path.join(os.path.dirname(__file__), "images/inconnu.jpg"),
                        documents(f"images/{login}.jpg"),
                    )
                else:
                    with open(documents(f"images/{login}.jpg"), "wb") as handler:
                        handler.write(content)

        def md5(fname):
            hash_md5 = hashlib.md5()
            with open(fname, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()

        async def download_session(loop):
            os.makedirs(documents("images"), exist_ok=True)
            async with aiohttp.ClientSession(loop=loop) as session:
                md5_inconnu = md5(
                    os.path.join(os.path.dirname(__file__), "images/inconnu.jpg")
                )
                for login in df.Login:
                    md5_curr = md5(documents(f"images/{login}.jpg"))
                    if (
                        not os.path.exists(documents(f"images/{login}.jpg"))
                        or md5_curr == md5_inconnu
                    ):
                        await download_image(session, login)

        # Getting images
        df = pd.read_excel(xls_merge)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(download_session(loop))

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
        latex_jinja_env.filters["escape_tex"] = escape_tex

        temp_dir = tempfile.mkdtemp()
        tmpl = latex_jinja_env.get_template("trombinoscope_template_2.tex.jinja2")

        # On vérifie que GROUPBY et SUBGROUPBY sont licites
        if groupby == "all":
            groupby = None
        else:
            check_columns(df, groupby, file=xls_merge)

        if subgroupby is not None:
            check_columns(df, subgroupby, file=xls_merge)

        # Diviser par groupe de TP/TP
        for title, group in df.groupby(groupby or (lambda x: "all")):

            # Diviser par binomes, sous-groupes
            dff = group.groupby(subgroupby or (lambda x: 0))

            # Nom de fichier
            if len(dff) == 1:
                fn = title + ".pdf"
            else:
                fn = title + "_" + subgroupby + ".pdf"
            data = []
            # Intérer sur ces sous-groupes des groupes de TP/TD
            for name, df_group in dff:
                group = {}
                if len(dff) != 1:
                    group["title"] = name

                rows = []
                dfs = df_group.sort_values(["Nom", "Prénom"])
                # Grouper par WIDTH sur une ligne si plus de WIDTH
                for _, df_row in dfs.groupby(np.arange(len(df_group.index)) // width):
                    cells = []
                    for _, row in df_row.iterrows():
                        path = os.path.abspath(documents(f'images/{row["Login"]}.jpg'))
                        cell = {
                            "name": row["Prénom"],
                            "lastname": row["Nom"],
                            "photograph": path,
                        }
                        cells.append(cell)
                    rows.append(cells)

                group["rows"] = rows
                data.append(group)

            tex = tmpl.render(title=title, data=data, width="c" * width)
            # with open(target0+'.tex', 'w') as fd:
            #     fd.write(tex)

            pdf = latex.build_pdf(tex)
            pdf.save_to(os.path.join(temp_dir, fn))

        # with Output(fn) as target0:
        #     pdf.save_to(target0())
        with Output(target) as target0:
            files = glob.glob(os.path.join(temp_dir, "*.pdf"))
            if len(files) == 1:
                shutil.move(files[0], target0())
            else:
                with zipfile.ZipFile(target0(), "w") as z:
                    for filepath in files:
                        z.write(filepath, os.path.basename(filepath))

    args = parse_args(
        task_pdf_trombinoscope,
        argument('-g', '--group', required=True),
        argument('-s', '--subgroup', required=False, default=None)
    )

    for planning, uv, info in selected_uv():
        dep = generated(task_xls_student_data_merge.target, **info)
        if args.group == 'all':
            if args.subgroup is not None:
                target = generated(f"trombi_all_{args.subgroup}.pdf", **info)
            else:
                target = generated(f"trombi_all.pdf", **info)
        else:
            if args.subgroup is not None:
                target = generated(f"trombi_{args.group}_{args.subgroup}.zip", **info)
            else:
                target = generated(f"trombi_{args.group}.zip", **info)

        yield {
            "name": f"{planning}_{uv}",
            "file_dep": [dep],
            "targets": [target],
            "actions": [(pdf_trombinoscope, [dep, target, args.group, args.subgroup, 5])],
            "uptodate": [False],
            "verbosity": 2,
        }


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
        check_columns(df, group, file=xls_merge)

        template = "attendance_list.tex.jinja2"

        pdfs = []
        for gn, group in df.groupby(group):
            group = group.sort_values(["Nom", "Prénom"])
            kwargs = {
                "group": f"Groupe: {gn}",
                "filename": f"{gn}.pdf"
            }
            pdf = pdf_attendance_list_render(group, template, **kwargs)
            pdfs.append(pdf)

        with Output(target) as target0:
            with zipfile.ZipFile(target0(), "w") as z:
                for filepath in pdfs:
                    z.write(filepath, os.path.basename(filepath))

    args = parse_args(
        task_pdf_attendance_list,
        argument('-g', '--group', required=True)
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
        argument('-c', '--course', required=True),
        argument('-n', '--slots', default=14)
    )

    planning, uv, info = get_unique_uv()
    xls_merge = generated(task_xls_student_data_merge.target, **info)
    target = generated(f"attendance_{args.course}_full.zip", **info)
    kwargs = {**info, "nslot": args.slots, "ctype": args.course}
    return {
        "file_dep": [xls_merge],
        "targets": [target],
        "actions": [(pdf_attendance_full, [xls_merge, target], kwargs)],
    }


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
        'file_dep': [xls_merge],
        'targets': [target],
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
        task_pdf_attendance_full,
        argument('-e', '--exam', required=True),
    )

    planning, uv, info = get_unique_uv()
    target = generated(f"{args.exam}_présence_%s.pdf", **info)

    return {
        "targets": [target],
        "actions": [(generate_attendance_sheets, [target])],
    }
