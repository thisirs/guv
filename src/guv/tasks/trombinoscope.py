"""
Ce module rassemble les tâches de création de trombinoscopes en
fonction de groupes de Cours/TD/TP ou de projet.
"""

import base64
import getpass
import json
import os
import random
import re
import shutil
from urllib.parse import parse_qs, urlparse

import guv
import mechanicalsoup
import numpy as np

from ..logger import logger
from ..utils import argument, generate_groupby, normalize_string, sort_values
from ..utils_config import render_from_contexts
from .base import CliArgsMixin, UVTask
from .internal import XlsStudentData


def get_random():
    # Generate 7 random numbers between 0 and 255
    random_numbers = [random.randint(0, 255) for _ in range(17)]

    # Convert each number to its hexadecimal representation and remove the '0x' prefix
    hex_string = ''.join([hex(num)[2:].zfill(2) for num in random_numbers])

    # Generate a random string of length 17 from the string of characters
    char_string = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    random_string = ''.join(random.choices(char_string, k=7))

    return hex_string + random_string


class NgApplisBrowser():
    def __init__(self):
        self.browser = mechanicalsoup.Browser(soup_config={'features': 'lxml'})
        self.is_authenticated = False

    def _authenticate(self):
        nonce = get_random()
        state = get_random()
        login_page = self.browser.get(f"https://cas.utc.fr/cas/oidc/oidcAuthorize?client_id=piaPROD&redirect_uri=https://ngapplis.utc.fr/trombiuv&response_type=id_token&scope=openid+profile&nonce={nonce}&state={state}")

        # Ask for the username
        username = input("Enter your username: ")

        # Safely ask for the password without showing it in the console
        password = getpass.getpass("Enter your password: ")

        login_form = mechanicalsoup.Form(login_page.soup.select_one("#fm1"))
        login_form.input({"username": username, "password": password})

        # Submit form, redirected to https://ngapplis.utc.fr/trombiuv/
        self.browser.submit(login_form, login_page.url)

        nonce = get_random()
        page = self.browser.get(f"https://cas.utc.fr/cas/oidc/oidcAuthorize?client_id=piaPROD&redirect_uri=https://ngapplis.utc.fr/trombiuv&response_type=id_token&scope=openid+profile&nonce={nonce}&state={state}")

        parsed_url = urlparse(page.url)
        fragment = parsed_url.fragment  # This gets everything after '#'

        # Parse the fragment into key-value pairs if it's & separated
        parameters = parse_qs(fragment)

        access_token = parameters["access_token"][0]
        self.browser.session.headers.update({"Authorization": "Bearer " + access_token})
        self.is_authenticated = True

    def get(self, url):
        if not self.is_authenticated:
            self._authenticate()
        return self.browser.get(url)


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

        self.xls_merge = XlsStudentData.target_from(**self.info)
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

        self.target = self.build_target(target_name=normalize_string(target, type="file_no_space"))
        self.width = 5

    def run(self):
        # On vérifie que GROUPBY et SUBGROUPBY sont licites
        df = XlsStudentData.read_target(self.xls_merge)

        if self.groupby is not None:
            self.check_if_present(
                df, self.groupby, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
            )

        if self.subgroupby is not None:
            self.check_if_present(
                df, self.subgroupby, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
            )

        self.download_photo(df)
        contexts = self.generate_contexts(df)
        render_from_contexts(
            self.template_file, contexts, save_tex=self.save_tex, target=self.target
        )

    def download_photo(self, df):
        browser = NgApplisBrowser()

        os.makedirs(os.path.join(self.settings.SEMESTER_DIR, "documents/images/"), exist_ok=True)
        URL = "https://webservices.utc.fr/api/v1/trombi/onebylogin/{login}"
        for login in df["Login"]:
            fp = os.path.join(self.settings.SEMESTER_DIR, f"documents/images/{login}.png")

            if not os.path.exists(fp):
                logger.debug("Photo pour `%s` inexistante, téléchargement", login)

                page = browser.get(URL.format(login=login))
                json_string = page.content.decode('utf-8')
                json_data = json.loads(json_string)
                base64_string = json_data["photo"]
                if base64_string is None:
                    logger.debug("Photo inexistante pour `%s`", login)
                    shutil.copyfile(os.path.join(guv.__path__[0], "images", "inconnu.jpg"), fp)
                else:
                    image_data = base64.b64decode(base64_string)
                    with open(fp, "wb") as file:
                        file.write(image_data)

    def student_context(self, row):
        """Retourne le contexte d'un étudiant pour Jinja2"""

        path = os.path.abspath(
            os.path.join(
                self.settings.SEMESTER_DIR, "documents", "images", f'{row["Login"]}.png'
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

    def generate_contexts(self, df):
        # Diviser par groupe de TD/TP
        for name_group, df_group in generate_groupby(df, self.groupby):

            # Contexte à passer au gabarit Jinja2
            context = {
                "name_group": name_group or self.uv,
                "width": "c" * self.width,
                "filename_no_ext": re.sub(r"\W+", "-", name_group) if name_group else "all"
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


