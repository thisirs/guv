"""
Ce module rassemble les tâches de création d'un fichier Excel central
sur l'effectif d'une UV.
"""

import getpass
import os
import smtplib

import jinja2
import openpyxl
import pandas as pd

from ..openpyxl_patched import fixit

fixit(openpyxl)

from ..exceptions import GuvUserError
from ..logger import logger
from ..utils import argument, normalize_string
from ..utils_config import Output, ask_choice
from .base import CliArgsMixin, UVTask
from .internal import XlsStudentData


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
        self.xls_merge = XlsStudentData.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.parse_args()
        self.target = self.build_target(group=normalize_string(self.group, type="file"))

    def run(self):
        df = XlsStudentData.read_target(self.xls_merge)
        self.check_if_present(
            df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
        )

        df_group = pd.DataFrame({
            "Pre-assign Room Name": df[self.group],
            "Email Address": df["Courriel"]
        })
        df_group = df_group.sort_values("Pre-assign Room Name")
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
        self.xls_merge = XlsStudentData.target_from(**self.info)
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
        df = XlsStudentData.read_target(self.xls_merge)

        with open(self.template, "r") as file_:
            if not file_.readline().startswith("Subject:"):
                raise GuvUserError("Le message doit commencer par \"Subject:\"")

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
            raise GuvUserError("Pas de message à envoyer")

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


