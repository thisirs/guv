import os
import hashlib
import shutil
import glob
import browser_cookie3
import pandas as pd
import numpy as np
import asyncio
import aiohttp
import jinja2
import tempfile
import latex
import zipfile

from .utils import (
    Output,
    documents,
    generated,
    selected_uv,
    escape_tex,
    argument,
    parse_args,
    actionfailed_on_exception,
    taskfailed_on_exception,
    check_columns,
)
from .dodo_students import XlsStudentDataMerge

URL = 'https://demeter.utc.fr/portal/pls/portal30/portal30.get_photo_utilisateur?username='


@actionfailed_on_exception
def task_pdf_trombinoscope():
    """Fichier PDF des trombinoscopes par groupes et/ou sous-groupes"""

    @taskfailed_on_exception
    def pdf_trombinoscope(xls_merge, target, groupby, subgroupby, width):
        # On vérifie que GROUPBY et SUBGROUPBY sont licites
        df = pd.read_excel(xls_merge)
        if groupby == "all":
            groupby = None
        else:
            check_columns(df, groupby, file=xls_merge)

        if subgroupby is not None:
            check_columns(df, subgroupby, file=xls_merge)

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
            cj = browser_cookie3.firefox()
            cookies = {c.name: c.value for c in cj if "demeter.utc.fr" in c.domain}
            async with aiohttp.ClientSession(loop=loop, cookies=cookies) as session:
                md5_inconnu = md5(
                    os.path.join(os.path.dirname(__file__), "images/inconnu.jpg")
                )
                for login in df.Login:
                    if not os.path.exists(documents(f"images/{login}.jpg")):
                        await download_image(session, login)
                    else:
                        md5_curr = md5(documents(f"images/{login}.jpg"))
                        if md5_curr == md5_inconnu:
                            await download_image(session, login)

        # Getting images
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

                        if "Numéro d'identification" in row:
                            cell.update(
                                {
                                    "moodle_id": row["Numéro d'identification"],
                                    "link": "https://demeter.utc.fr/portal/pls/portal30/etudiants.CONSULT_DODDIER_ETU_ETU_DYN.show?p_arg_names=p_etudiant_cle&p_arg_values=%(moodle_id)s",
                                }
                            )

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
        argument(
            "-g",
            "--group",
            required=True,
            help="Nom de colonne pour réaliser un groupement",
        ),
        argument(
            "-s",
            "--subgroup",
            required=False,
            default=None,
            help="Nom de colonne des sous-groupes (binômes, trinômes)",
        ),
    )

    for planning, uv, info in selected_uv():
        dep = generated(XlsStudentDataMerge.target, **info)
        if args.group == "all":
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
            "actions": [
                (pdf_trombinoscope, [dep, target, args.group, args.subgroup, 5])
            ],
            "uptodate": [False],
            "verbosity": 2,
        }
