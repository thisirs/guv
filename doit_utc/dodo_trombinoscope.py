"""
Fichier qui regroupe des tâches de création de trombinoscopes en
fonction de groupes de Cours/TD/TP ou de projet.
"""

import os
import hashlib
import shutil
import glob
import tempfile
import zipfile
import asyncio
import aiohttp
import pandas as pd
import numpy as np
import jinja2
import browser_cookie3
import latex

from .config import settings
from .utils_config import Output, documents, generated
from .utils import sort_values, escape_tex, argument, check_columns
from .dodo_students import XlsStudentDataMerge
from .tasks import UVTask, CliArgsMixin

URL = 'https://demeter.utc.fr/portal/pls/portal30/portal30.get_photo_utilisateur?username='


class PdfTrombinoscope(UVTask, CliArgsMixin):
    """Fichier PDF des trombinoscopes par groupes et/ou sous-groupes"""

    always_make = True
    cli_args = (
        argument(
            "-g",
            "--group",
            dest="groupby",
            required=True,
            help="Nom de colonne pour réaliser un groupement",
        ),
        argument(
            "-s",
            "--subgroup",
            dest="subgroupby",
            required=False,
            default=None,
            help="Nom de colonne des sous-groupes (binômes, trinômes)",
        ),
    )

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)

        self.xls_merge = generated(XlsStudentDataMerge.target, **info)
        if self.groupby == "all":
            if self.subgroupby is not None:
                self.target = generated(f"trombi_all_{self.subgroupby}.pdf", **info)
            else:
                self.target = generated(f"trombi_all.pdf", **info)
        else:
            if self.subgroupby is not None:
                self.target = generated(f"trombi_{self.groupby}_{self.subgroupby}.zip", **info)
            else:
                self.target = generated(f"trombi_{self.groupby}.zip", **info)

        self.file_dep = [self.xls_merge]
        self.width = 5

    def run(self):
        # On vérifie que GROUPBY et SUBGROUPBY sont licites
        df = pd.read_excel(self.xls_merge, engine="openpyxl")
        if self.groupby == "all":
            self.groupby = None
        else:
            check_columns(df, self.groupby, file=self.xls_merge, base_dir=settings.BASE_DIR)

        if self.subgroupby is not None:
            check_columns(df, self.subgroupby, file=self.xls_merge, base_dir=settings.BASE_DIR)

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
        for title, group in df.groupby(self.groupby or (lambda x: "all")):

            # Diviser par binomes, sous-groupes
            dff = group.groupby(self.subgroupby or (lambda x: 0))

            # Nom de fichier
            if len(dff) == 1:
                fn = title + ".pdf"
            else:
                fn = title + "_" + self.subgroupby + ".pdf"
            data = []
            # Insérer sur ces sous-groupes des groupes de TP/TD
            for name, df_group in dff:
                group = {}
                if len(dff) != 1:
                    group["title"] = name

                rows = []
                dfs = sort_values(df_group, ["Nom", "Prénom"])
                # Grouper par WIDTH sur une ligne si plus de WIDTH
                for _, df_row in dfs.groupby(np.arange(len(df_group.index)) // self.width):
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

            tex = tmpl.render(title=title, data=data, width="c" * self.width)
            # with open(target0+'.tex', 'w') as fd:
            #     fd.write(tex)

            pdf = latex.build_pdf(tex)
            pdf.save_to(os.path.join(temp_dir, fn))

        # with Output(fn) as target0:
        #     pdf.save_to(target0())
        with Output(self.target) as target0:
            files = glob.glob(os.path.join(temp_dir, "*.pdf"))
            if len(files) == 1:
                shutil.move(files[0], target0())
            else:
                with zipfile.ZipFile(target0(), "w") as z:
                    for filepath in files:
                        z.write(filepath, os.path.basename(filepath))
