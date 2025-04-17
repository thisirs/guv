"""
Ce module rassemble les tâches de création d'un fichier Excel central
sur l'effectif d'une UV.
"""

import getpass
import os
import re
import shlex
import smtplib
import sys
import textwrap

import jinja2
import openpyxl
import pandas as pd

from ..openpyxl_patched import fixit

fixit(openpyxl)

from ..logger import logger
from ..utils import argument, normalize_string
from ..utils_config import Output, ask_choice, check_if_present, rel_to_dir
from .base import CliArgsMixin, UVTask
from .internal import XlsStudentDataMerge


class ZoomBreakoutRooms(UVTask, CliArgsMixin):
    """Crée un fichier csv prêt à charger sur Zoom pour faire des groupes"""

    target_dir = "generated"
    target_name = "zoom_breakout_rooms_{group}.csv"
    cli_args = (
        argument(
            "group",
            help="Le nom de la colonne des groupes",
        ),
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.parse_args()
        self.target = self.build_target(group=normalize_string(self.group, type="file"))

    def run(self):
        df = XlsStudentDataMerge.read_target(self.xls_merge)
        check_if_present(
            df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
        )

        df_group = pd.DataFrame({
            "Pre-assign Room Name": df[self.group],
            "Email Address": df["Courriel"]
        })
        df_group = df_group.sort_values("Pre-assign Room Name")
        with Output(self.target, protected=True) as out:
            df_group.to_csv(out.target, index=False)


class MaggleTeams(UVTask, CliArgsMixin):
    """Crée un fichier csv prêt à charger sur django-maggle pour faire des groupes"""

    target_dir = "generated"
    target_name = "maggle_teams_{group}.csv"
    cli_args = (
        argument(
            "group",
            help="Le nom de la colonne des groupes",
        ),
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.parse_args()
        self.target = self.build_target(group=normalize_string(self.group, type="file"))

    def run(self):
        df = XlsStudentDataMerge.read_target(self.xls_merge)
        check_if_present(
            df,
            [
                "Login",
                "Courriel",
                self.group,
            ],
            file=self.xls_merge,
            base_dir=self.settings.SEMESTER_DIR,
        )

        df_group = df[["Nom", "Prénom", "Courriel", "Login", self.group]]
        with Output(self.target, protected=True) as out:
            df_group.to_csv(out.target, index=False)


class SendEmail(UVTask, CliArgsMixin):
    """Envoie de courriel à chaque étudiant.

    Le seul argument à fournir est un chemin vers un fichier servant
    de modèle pour les courriels. Si le fichier n'existe pas, un
    modèle par défaut est créé. Le modèle est au format Jinja2 et les
    variables de remplacement disponibles pour chaque étudiant sont
    les noms de colonnes dans le fichier ``effectif.xlsx``. Pour
    permettre l'envoi des courriels, il faut renseigner les variables
    ``LOGIN`` (login de connexion au serveur SMTP), ``FROM_EMAIL``
    l'adresse courriel d'envoi dans le fichier ``config.py``. Les
    variables ``SMTP_SERVER`` et ``PORT`` (par défaut smtps.utc.fr et
    587).

    {options}

    Exemples
    --------

    .. code:: bash

       guv send_email documents/email_body

    avec ``documents/email_body`` qui contient :

    .. code:: text

       Subject: Note

       Bonjour {{ Prénom }},

       Vous faites partie du groupe {{ group_projet }}.

       Cordialement,

       guv

    """

    uptodate = False
    cli_args = (
        argument(
            "template",
            help="Le chemin vers un modèle au format Jinja2",
        ),
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.parse_args()

    def run(self):
        if os.path.exists(self.template):
            self.send_emails()
        else:
            self.create_template()

    def create_template(self):
        result = ask_choice(
            f"Le fichier {self.template} n'existe pas. Créer ? (y/n) ",
            {"y": True, "n": False},
        )
        if result:
            with open(self.template, "w") as file_:
                file_.write("Subject: le sujet\n\nle corps")

    def send_emails(self):
        df = XlsStudentDataMerge.read_target(self.xls_merge)

        with open(self.template, "r") as file_:
            if not file_.readline().startswith("Subject:"):
                raise Exception("Le message doit commencer par \"Subject:\"")

        jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader("./"), undefined=jinja2.StrictUndefined
        )
        message_tmpl = jinja_env.get_template(self.template)

        try:
            email_and_message = [
                (row["Courriel"], message_tmpl.render(row.to_dict()))
                for index, row in df.iterrows()
            ]
        except jinja2.exceptions.UndefinedError as e:
            raise e

        if len(email_and_message) == 0:
            raise Exception("Pas de message à envoyer")

        email, message = email_and_message[0]
        logger.info("Premier message à %s : \n%s", email, message)
        result = ask_choice(
            f"Envoyer les {len(email_and_message)} courriels ? (y/n) ",
            {"y": True, "n": False},
        )

        if result:
            from_email = self.settings.FROM_EMAIL

            with smtplib.SMTP(
                self.settings.SMTP_SERVER, port=self.settings.PORT
            ) as smtp:
                smtp.starttls()

                password = getpass.getpass("Mot de passe : ")
                smtp.login(self.settings.LOGIN, password)
                for email, message in email_and_message:
                    smtp.sendmail(from_addr=from_email, to_addrs=email, msg=message)


class PasswordFile(UVTask, CliArgsMixin):
    """Crée un fichier csv d'association entre étudiants et mots de passe."""

    target_name = "machine_password.csv"
    target_dir = "generated"
    cli_args = (
        argument(
            "file",
            help="Le chemin du fichier contenant les mots de passe"
        ),
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        # No targets to avoid circular deps in doit as we probably
        # want to aggregate target in effectif.xlsx
        self.targets = []

        self.parse_args()

    def run(self):
        df = XlsStudentDataMerge.read_target(self.xls_merge)
        df = df[["Nom", "Prénom", "Courriel"]]

        df_passwd = self.parse_passwd_file()
        df_passwd = df_passwd.iloc[:len(df.index)]

        # Before concat (see https://stackoverflow.com/a/32802014)
        df.reset_index(drop=True, inplace=True)
        df_passwd.reset_index(drop=True, inplace=True)

        df_concat = pd.concat((df, df_passwd), axis="columns")

        target = self.build_target()
        with Output(target, protected=True) as out:
            df_concat.to_csv(out.target, index=False)

        logger.info(self.message(target))

    def parse_passwd_file(self):
        if "RX_PASSWD" in self.settings:
            RX_PASSWD = re.compile(self.settings.RX_PASSWD)
        else:
            RX_PASSWD = re.compile(
                r"^"
                r"(?P<windows>[a-z0-9@]+)"
                r"\s+"
                r"(?P<unix>[a-z0-9]+)"
                r"\s+"
                r"(?P<passwd>[a-zA-Z0-9]+)"
                r"$"
            )

        def gen_data():
            with open(self.file, "r") as fd:
                for line in fd:
                    line = line.strip()
                    if not line:
                        continue

                    m = RX_PASSWD.match(line)
                    if m:
                        yield m.group("windows"), m.group("unix"), m.group("passwd")

        return pd.DataFrame(gen_data(), columns=["windows", "unix", "passwd"])

    def message(self, target):
        columns = ["windows", "unix", "passwd"]
        return textwrap.dedent("""\

        Pour agréger ce fichier au fichier central `effectif.xlsx`, ajouter :

        # Créé avec la commande : {command_line}
        DOCS.aggregate(
            "{filename}",
            on="Courriel",
            subset={columns}
        )

        dans le fichier `config.py` de l'UV/UE.
        """.format(**{
            "filename": rel_to_dir(target, self.settings.UV_DIR),
            "columns": columns,
            "command_line": "guv " + " ".join(map(shlex.quote, sys.argv[1:]))
        }))

