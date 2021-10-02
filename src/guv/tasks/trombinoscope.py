"""
Ce module rassemble les tâches de création de trombinoscopes en
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
import browser_cookie3
import latex
import guv

from ..utils_config import Output
from ..utils import sort_values, argument, check_columns, LaTeXEnvironment
from .students import XlsStudentDataMerge
from .base import UVTask, CliArgsMixin

URL = 'https://demeter.utc.fr/portal/pls/portal30/portal30.get_photo_utilisateur?username='


class PdfTrombinoscope(UVTask, CliArgsMixin):
    """Fichier PDF des trombinoscopes par groupes et/ou sous-groupes.

    {options}

    """

    always_make = True
    target_dir = "generated"
    cli_args = (
        argument(
            "-g",
            "--group",
            metavar="GROUP",
            dest="groupby",
            required=True,
            help="Nom de colonne utilisée pour réaliser le groupement. Un fichier pdf est généré pour chaque groupe. Lorsque le nom de groupe est ``all``, il y a un seul groupe (donc un seul fichier pdf) comportant la totalité des étudiants.",
        ),
        argument(
            "-s",
            "--subgroup",
            metavar="SUBGROUP",
            dest="subgroupby",
            required=False,
            default=None,
            help="Nom de colonne utilisée pour faire des sous-groupes (binômes, trinômes) parmi le groupement déjà existant.",
        ),
    )

    def setup(self):
        super().setup()

        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        if self.groupby == "all":
            if self.subgroupby is not None:
                target = "trombi_all_{subgroupby}.pdf"
            else:
                target = "trombi_all.pdf"
        else:
            if self.subgroupby is not None:
                target = "trombi_{groupby}_{subgroupby}.zip"
            else:
                target = "trombi_{groupby}.zip"

        self.target = self.build_target(target_name=target)
        self.width = 5

    def run(self):
        # On vérifie que GROUPBY et SUBGROUPBY sont licites
        df = pd.read_excel(self.xls_merge, engine="openpyxl")
        if self.groupby == "all":
            self.groupby = None
        else:
            check_columns(df, self.groupby, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR)

        if self.subgroupby is not None:
            check_columns(df, self.subgroupby, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR)

        async def download_image(session, login):
            url = URL + login
            async with session.get(url) as response:
                content = await response.content.read()
                fp = os.path.join(
                    self.settings.SEMESTER_DIR, f"documents/images/{login}.jpg"
                )
                if len(content) < 100:
                    shutil.copyfile(
                        os.path.join(guv.__path__[0], "images", "inconnu.jpg"),
                        fp
                    )
                else:
                    with open(fp, "wb") as handler:
                        handler.write(content)

        def md5(fname):
            hash_md5 = hashlib.md5()
            with open(fname, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()

        async def download_session(loop):
            os.makedirs(os.path.join(self.settings.SEMESTER_DIR, "documents", "images"), exist_ok=True)
            cj = browser_cookie3.firefox()
            cookies = {c.name: c.value for c in cj if "demeter.utc.fr" in c.domain}
            async with aiohttp.ClientSession(loop=loop, cookies=cookies) as session:
                md5_inconnu = md5(
                    os.path.join(guv.__path__[0], "images", "inconnu.jpg")
                )
                for login in df.Login:
                    fp = os.path.join(
                        self.settings.SEMESTER_DIR,
                        "documents",
                        "images",
                        "{login}.jpg"
                    )
                    if not os.path.exists(fp):
                        await download_image(session, login)
                    else:
                        md5_curr = md5(fp)
                        if md5_curr == md5_inconnu:
                            await download_image(session, login)

        # Getting images
        loop = asyncio.get_event_loop()
        loop.run_until_complete(download_session(loop))

        latex_env = LaTeXEnvironment()
        tmpl = latex_env.get_template("trombinoscope_template_2.tex.jinja2")
        temp_dir = tempfile.mkdtemp()

        # Diviser par groupe de TD/TP
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
                        path = os.path.abspath(
                            os.path.join(
                                self.settings.SEMESTER_DIR,
                                "documents",
                                "images",
                                f'{row["Login"]}.jpg'
                            )
                        )

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
