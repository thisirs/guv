"""
Ce module rassemble les tâches de création de trombinoscopes en
fonction de groupes de Cours/TD/TP ou de projet.
"""

import asyncio
import hashlib
import os
import shutil

import aiohttp
import browser_cookie3
import numpy as np
import pandas as pd

import guv

from ..utils import argument, generate_groupby, sort_values
from ..utils_config import ensure_present_columns, render_from_contexts
from .base import CliArgsMixin, UVTask
from .students import XlsStudentDataMerge

URL = 'https://demeter.utc.fr/portal/pls/portal30/portal30.get_photo_utilisateur?username='


class PdfTrombinoscope(UVTask, CliArgsMixin):
    """Fichier PDF des trombinoscopes par groupes et/ou sous-groupes.

    {options}

    Examples
    --------

    - Trombinoscope par groupe de TP :

      .. code:: bash

         guv pdf_trombinoscope --group TP

    - Trombinoscope par groupe de TP avec des groupes de projet dans
      chaque feuille :

      .. code:: bash

         guv pdf_trombinoscope --group TP --subgroup Projet

    """

    uptodate = True
    target_dir = "generated"
    template_file = "trombinoscope_template_2.tex.jinja2"
    cli_args = (
        argument(
            "-g",
            "--group",
            metavar="GROUP",
            dest="groupby",
            help="Nom de colonne utilisée pour réaliser le groupement. Un fichier pdf est généré pour chaque groupe. Lorsque le nom de groupe est ``all``, il y a un seul groupe (donc un seul fichier pdf) comportant la totalité des étudiants.",
        ),
        argument(
            "-s",
            "--subgroup",
            metavar="SUBGROUP",
            dest="subgroupby",
            help="Nom de colonne utilisée pour faire des sous-groupes (binômes, trinômes) parmi le groupement déjà existant.",
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
        if self.groupby is None:
            if self.subgroupby is not None:
                target = "trombi_all_{subgroupby}"
            else:
                target = "trombi_all"
        else:
            if self.subgroupby is not None:
                target = "trombi_{groupby}_{subgroupby}"
            else:
                target = "trombi_{groupby}"

        self.target = self.build_target(target_name=target)
        self.width = 5

    def run(self):
        # On vérifie que GROUPBY et SUBGROUPBY sont licites
        df = pd.read_excel(self.xls_merge, engine="openpyxl")
        if self.groupby is not None:
            ensure_present_columns(
                df, self.groupby, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
            )

        if self.subgroupby is not None:
            ensure_present_columns(
                df, self.subgroupby, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
            )

        self.download_images(df)
        contexts = self.generate_contexts(df)
        render_from_contexts(
            self.template_file, contexts, save_tex=self.save_tex, target=self.target
        )

    def student_context(self, row):
        """Retourne le contexte d'un édudiant pour Jinja2"""

        path = os.path.abspath(
            os.path.join(
                self.settings.SEMESTER_DIR, "documents", "images", f'{row["Login"]}.jpg'
            )
        )

        context = {
            "name": row["Prénom"],
            "lastname": row["Nom"],
            "photograph": path,
        }

        if "Numéro d'identification" in row:
            context.update(
                {
                    "moodle_id": row["Numéro d'identification"],
                    "link": "https://demeter.utc.fr/portal/pls/portal30/etudiants.CONSULT_DODDIER_ETU_ETU_DYN.show?p_arg_names=p_etudiant_cle&p_arg_values=%(moodle_id)s",
                }
            )

        return context

    def download_images(self, df):
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
                        f"{login}.jpg"
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

    def generate_contexts(self, df):
        # Diviser par groupe de TD/TP
        for name_group, df_group in generate_groupby(df, self.groupby):

            # Contexte à passer au gabarit Jinja2
            context = {
                "name_group": name_group or self.uv,
                "width": "c" * self.width,
                "filename_no_ext": name_group or "all"
            }

            # Diviser par groupes de projets à l'intérieur de chaque groupe
            subgroups = {}
            for name_subgroup, df_subgroup in generate_groupby(df_group, self.subgroupby):
                dfs = sort_values(df_subgroup, ["Nom", "Prénom"])

                # Grouper par WIDTH sur une ligne si plus de WIDTH
                rows = [
                    [self.student_context(row) for _, row in df_row.iterrows()]
                    for _, df_row in dfs.groupby(
                        np.arange(len(dfs.index)) // self.width
                    )
                ]

                subgroups[name_subgroup] = rows

            context["subgroups"] = subgroups

            yield context


