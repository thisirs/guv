"""
Ce module rassemble les tâches de création d'un fichier Excel central
sur l'effectif d'une UV.
"""

import getpass
import math
import os
import random
import re
import smtplib

import jinja2
import numpy as np
import openpyxl
import pandas as pd
from unidecode import unidecode

from ..openpyxl_patched import fixit

fixit(openpyxl)

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows

from ..exceptions import ImproperlyConfigured
from ..helpers import Documents, id_slug, Aggregator
from ..logger import logger
from ..utils import argument, sort_values
from ..utils_config import Output, check_if_present, rel_to_dir, ask_choice
from .base import CliArgsMixin, UVTask


class CsvInscrits(UVTask):
    """Construit un fichier CSV à partir des données brutes de la promo fournies par l'UTC"""

    hidden = True
    target_name = "inscrits.csv"
    target_dir = "generated"
    unique_uv = False

    def setup(self):
        super().setup()
        self.target = self.build_target()
        utc_listing_fn = self.settings.AFFECTATION_LISTING
        if utc_listing_fn is not None:
            self.utc_listing = os.path.join(
                self.settings.SEMESTER_DIR, self.uv, utc_listing_fn
            )
            self.file_dep = [self.utc_listing]
        else:
            self.utc_listing = None
            self.file_dep = []

    def parse_UTC_listing(self):
        """Parse `utc_listing` into DataFrame"""

        if "RX_STU" in self.settings:
            RX_STU = re.compile(self.settings.RX_STU)
        else:
            # 042   NOM PRENOM            GI02
            RX_STU = re.compile(
                r"^\s*"
                r"\d{3}"
                r"\s{3}"
                r"(?P<name>.{23})"
                r"\s{3}"
                r"(?P<branche>[A-Z]{2})"
                r"(?P<semestre>[0-9]{2})"
                r"$"
            )

        if "RX_UV" in self.settings:
            RX_UV = re.compile(self.settings.RX_UV)
        else:
            # SY19       C 1   ,PL.MAX= 73 ,LIBRES=  0 ,INSCRITS= 73  H=MERCREDI 08:00-10:00,F1,S=
            RX_UV = re.compile(
                r"^\s*"
                r"(?P<uv>\w+)"
                r"\s+"
                r"(?P<course>[CTD])"
                r"\s*"
                r"(?P<number>[0-9]+)"
                r"\s*"
                r"(?P<week>[AB])?"
            )

        with open(self.utc_listing, "r") as fd:
            course_name = course_type = None
            rows = []
            for line in fd:
                m = RX_UV.match(line)
                if m:
                    number = m.group("number") or ""
                    week = m.group("week") or ""
                    course = m.group("course") or ""
                    course_name = course + number + week
                    course_type = {"C": "Cours", "D": "TD", "T": "TP"}[course]
                else:
                    m = RX_STU.match(line)
                    if m:
                        name = m.group("name").strip()
                        spe = m.group("branche")
                        sem = int(m.group("semestre"))
                        if spe == "HU":
                            spe = "HuTech"
                        elif spe == "MT":
                            spe = "ISC"
                        rows.append(
                            {
                                "Name": name,
                                "course_type": course_type,
                                "course_name": course_name,
                                "Branche": spe,
                                "Semestre": sem,
                            }
                        )
                    elif line.strip():
                        logger.warning("La ligne ci-après n'est pas reconnue :")
                        logger.warning(line.strip())

        df = pd.DataFrame(rows)
        df = pd.pivot_table(
            df,
            columns=["course_type"],
            index=["Name", "Branche", "Semestre"],
            values="course_name",
            aggfunc="first",
        )
        df = df.reset_index()

        # Il peut arriver qu'un créneau A/B ne soit pas marqué comme tel
        # car il n'a pas de pendant pour l'autre semaine. On le fixe donc
        # manuellement à A ou B.
        if "TP" in df.columns:
            semAB = [i for i in df.TP.unique() if re.match("T[0-9]{,2}[AB]", i)]
            if semAB:
                gr = [i for i in df.TP.unique() if re.match("^T[0-9]{,2}$", i)]
                rep = {}
                for g in gr:
                    while True:
                        try:
                            choice = input(f"Semaine pour le créneau {g} (A ou B) ? ")
                            if choice.upper() in ["A", "B"]:
                                rep[g] = g + choice.upper()
                            else:
                                raise ValueError
                        except ValueError:
                            continue
                        else:
                            break

                df = df.replace({"TP": rep})
        return df

    def run(self):
        if self.utc_listing is None:
            raise ImproperlyConfigured(
                "La variable 'AFFECTATION_LISTING' n'est pas renseignée"
            )
        if not os.path.exists(self.utc_listing):
            raise Exception("Le fichier '{0}' n'existe pas".format(
                rel_to_dir(self.utc_listing, self.settings.SEMESTER_DIR)
            ))
        df = self.parse_UTC_listing()
        with Output(self.target) as out:
            df.to_csv(out.target, index=False)


class XlsStudentData(UVTask):
    """Construit le fichier Excel des données étudiants fournies par l'UTC

    Les données utilisées sont le fichier disponible sur l'ENT de
    l'effectif officiel de l'UV repéré par la variable ``ENT_LISTING``
    dans le fichier ``config.py`` de l'UV, le fichier des affectations aux
    créneaux de Cours/TD/TP repéré par la variable ``AFFECTATION_LISTING``
    dans le fichier ``config.py`` de l'UV et le fichier Moodle des
    inscrits à l'UV (si disponible) repéré par la variable
    ``MOODLE_LISTING`` dans le fichier ``config.py`` de l'UV.
    """

    hidden = True
    target_dir = "generated"
    target_name = "student_data.xlsx"
    unique_uv = False

    def setup(self):
        super().setup()
        self.file_dep = []
        self.target = self.build_target()

        if "ENT_LISTING" in self.settings and self.settings.ENT_LISTING:
            self.extraction_ENT = os.path.join(
                self.settings.SEMESTER_DIR, self.uv, self.settings.ENT_LISTING
            )
            self.file_dep.append(self.extraction_ENT)
        else:
            self.extraction_ENT = None

        if self.settings.AFFECTATION_LISTING is not None:
            self.csv_UTC = CsvInscrits.target_from(**self.info)
            self.file_dep.append(self.csv_UTC)
        else:
            self.csv_UTC = None

        if "MOODLE_LISTING" in self.settings and self.settings.MOODLE_LISTING:
            self.csv_moodle = os.path.join(
                self.settings.SEMESTER_DIR, self.uv, self.settings.MOODLE_LISTING
            )
            self.file_dep.append(self.csv_moodle)
        else:
            self.csv_moodle = None

    def run(self):
        if self.extraction_ENT is not None:
            logger.info(
                "Chargement des données issues de l'ENT: `%s`",
                rel_to_dir(self.extraction_ENT, self.settings.cwd),
            )
            if not os.path.isfile(self.extraction_ENT):
                raise Exception(
                    "Le chemin `{}` n'existe pas ou n'est pas un fichier".format(
                        rel_to_dir(self.extraction_ENT, self.settings.cwd)
                    )
                )

            df = self.load_ENT_data()

            if self.csv_moodle is not None:
                logger.info(
                    "Ajout des données issues de Moodle: `%s`",
                    rel_to_dir(self.csv_moodle, self.settings.cwd),
                )

                if not os.path.isfile(self.csv_moodle):
                    raise Exception(
                        "Le chemin `{}` n'existe pas ou n'est pas un fichier".format(
                            rel_to_dir(self.csv_moodle, self.settings.cwd)
                        )
                    )

                df_moodle = self.load_moodle_data()
                df = self.add_moodle_data(df, df_moodle)
        else:
            if self.csv_moodle is None:
                raise Exception("Pas de fichier `ENT_LISTING` ni `MOODLE_LISTING`")
            logger.info("Chargement des données issues de Moodle")
            df = self.load_moodle_data()

        if self.csv_UTC is not None:
            logger.info(
                "Ajout des affectations aux Cours/TD/TP : `%s`",
                rel_to_dir(self.csv_UTC, self.settings.cwd),
            )
            df = self.add_UTC_data(df, self.csv_UTC)

        dff = sort_values(df, ["Nom", "Prénom"])

        with Output(self.target) as out:
            dff.to_excel(out.target, index=False)

    def load_ENT_data(self):
        try:
            return self.load_ENT_data_old()
        except pd.errors.ParserError as e:
            return self.load_ENT_data_new()

    def load_ENT_data_new(self):
        df = pd.read_excel(self.extraction_ENT)

        # Split information in 2 columns
        df[["Branche", "Semestre"]] = df.pop('Spécialité').str.extract(
            '(?P<Branche>[a-zA-Z]+) *(?P<Semestre>[0-9]+)',
            expand=True
        )
        df["Semestre"] = pd.to_numeric(df['Semestre'])

        # Drop unrelevant columns
        df = df.drop(['Réussite', 'Résultat ECTS', 'Mention'], axis=1)

        return df

    def load_ENT_data_old(self):
        df = pd.read_csv(self.extraction_ENT, sep="\t", encoding='ISO_8859_1')

        # Split information in 2 columns
        df[["Branche", "Semestre"]] = df.pop('Spécialité 1').str.extract(
            '(?P<Branche>[a-zA-Z]+) *(?P<Semestre>[0-9]+)',
            expand=True
        )
        df["Semestre"] = pd.to_numeric(df['Semestre'])

        # Drop unrelevant columns
        df = df.drop(['Inscription', 'Spécialité 2', 'Résultat ECTS', 'UTC', 'Réussite', 'Statut'], axis=1)

        # Drop unamed columns
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

        return df

    def load_moodle_data(self):
        fn = self.csv_moodle

        if fn.endswith(".csv"):
            df = pd.read_csv(fn)
        elif fn.endswith(".xlsx") or fn.endswith(".xls"):
            df = pd.read_excel(fn, engine="openpyxl")
        else:
            raise Exception("Format de fichier non reconnu")

        nans = df["Nom"].isna() | df["Prénom"].isna()
        if sum(nans) != 0:
            logger.warning(
                "%d enregistrement(s) ont été ignorés dans le fichier `%s`",
                sum(nans),
                rel_to_dir(self.csv_moodle, self.settings.cwd)
            )
            df = df.drop(df[nans].index)

        # On laisse tomber les colonnes inintéressantes
        df = df.drop(
            ["Institution", "Département", "Dernier téléchargement depuis ce cours"],
            axis=1,
        )

        return df

    def add_moodle_data(self, df, df_moodle):
        """Incorpore les données du fichier extrait de Moodle"""

        if "Courriel" not in df.columns:
            raise Exception("La colonne `Courriel` n'est pas présente dans le fichier central")

        moodle_short_email = re.match(f"^\w+@", df_moodle.iloc[0]["Adresse de courriel"]) is not None
        ent_short_email = re.match(f"^\w+@", df.iloc[0]["Courriel"]) is not None

        if moodle_short_email ^ ent_short_email:
            logger.warning("Les adresses courriels sont dans un format différent, agrégation avec les colonnes `Nom` et `Prénom`")
            left_on = right_on = id_slug("Nom", "Prénom")
        else:
            left_on = "Courriel"
            right_on = "Adresse de courriel"

        # Outer aggregation only to handle specifically mismatches
        agg = Aggregator(
            left_df=df,
            right_df=df_moodle,
            left_on=left_on,
            right_on=right_on,
            right_suffix="_moodle"
        )
        agg.outer_aggregate()

        # Warn of any mismatch
        lo = agg.outer_merged_df.loc[agg.outer_merged_df["_merge"] == "left_only"]
        for index, row in lo.iterrows():
            fullname = row["Nom"] + " " + row["Prénom"]
            logger.warning("`%s` n'est pas présent dans les données Moodle", fullname)

        ro = agg.outer_merged_df.loc[agg.outer_merged_df["_merge"] == "right_only"]
        for index, row in ro.iterrows():
            fullname = row["Nom_moodle"] + " " + row["Prénom_moodle"]
            logger.warning("`%s` n'est pas présent dans le fichier central", fullname)

        # Base dataframe to add row to
        df_both = agg.outer_merged_df.loc[agg.outer_merged_df["_merge"] == "both"]

        # Ask user to do the matching
        for index, row in lo.iterrows():
            if len(ro.index) != 0:
                fullname = row["Nom"] + " " + row["Prénom"]
                logger.info("Recherche de correspondance pour `%s` :", fullname)
                for i, (index_ro, row_ro) in enumerate(ro.iterrows()):
                    fullname_ro = row_ro["Nom_moodle"] + " " + row_ro["Prénom_moodle"]
                    print(f"  ({i}) {fullname_ro}")

                choice = ask_choice(
                    "Choix ? (entrée si pas de correspondance) ",
                    {**{str(i): i for i in range(len(ro.index))}, "": None}
                )

                if choice is not None:
                    row_merge = lo.loc[index, :].combine_first(ro.iloc[choice, :])
                    ro = ro.drop(index=ro.iloc[[choice]].index)
                    row_merge["_merge"] = "both"
                    df_both = pd.concat((df_both, row_merge.to_frame().T))
                else:
                    row_merge = lo.loc[index, :].copy()
                    row_merge["_merge"] = "both"
                    df_both = pd.concat((df_both, row_merge.to_frame().T))
            else:
                row_merge = lo.loc[index, :].copy()
                row_merge["_merge"] = "both"
                df_both = pd.concat((df_both, row_merge.to_frame().T))

        return agg.clean_merge(df_both)

    def add_UTC_data(self, df, fn):
        "Incorpore les données Cours/TD/TP des inscrits UTC"

        if "Nom" not in df.columns:
            raise Exception("Pas de colonne 'Nom' pour agréger les données")
        if "Prénom" not in df.columns:
            raise Exception("Pas de colonne 'Prénom' pour agréger les données")

        # Données issues du fichier des affectations au Cours/TD/TP
        dfu = pd.read_csv(fn)

        fullnames = df["Nom"] + " " + df["Prénom"]

        def slug(e):
            return unidecode(e.upper()[:23].strip())

        df["fullname_slug"] = fullnames.apply(slug)

        dfr = pd.merge(
            df,
            dfu,
            suffixes=("", "_utc"),
            how="outer",
            left_on=["fullname_slug", "Branche", "Semestre"],
            right_on=["Name", "Branche", "Semestre"],
            indicator=True,
        )

        dfr_clean = dfr.loc[dfr["_merge"] == "both"]

        lo = dfr.loc[dfr["_merge"] == "left_only"]
        for index, row in lo.iterrows():
            key = row["fullname_slug"]
            branch = row["Branche"]
            semester = row["Semestre"]
            logger.warning("(`%s`, `%s`, `%s`) présent dans `ENT_LISTING` mais pas dans `AFFECTATION_LISTING`", key, branch, semester)

        ro = dfr.loc[dfr["_merge"] == "right_only"]
        for index, row in ro.iterrows():
            key = row["Name"]
            branch = row["Branche"]
            semester = row["Semestre"]
            logger.warning("(`%s`, `%s`, `%s`) présent dans `AFFECTATION_LISTING` mais pas dans `ENT_LISTING`", key, branch, semester)

        # Trying to merge manually lo and ro
        for index, row in lo.iterrows():
            if len(ro.index) != 0:
                fullname = row["Nom"] + " " + row["Prénom"]
                logger.info("Recherche de correspondance pour `%s` :", fullname)

                for i, (index_ro, row_ro) in enumerate(ro.iterrows()):
                    fullname_ro = row_ro["Name"]
                    print(f"  ({i}) {fullname_ro}")

                choice = ask_choice(
                    "Choix ? (entrée si pas de correspondance) ",
                    {**{str(i): i for i in range(len(ro.index))}, "": None}
                )

                if choice is not None:
                    row_merge = lo.loc[index, :].combine_first(ro.iloc[choice, :])
                    ro = ro.drop(index=ro.iloc[[choice]].index)
                    row_merge["_merge"] = "both"
                    dfr_clean = pd.concat((dfr_clean, row_merge.to_frame().T))
                else:
                    row_merge = lo.loc[index, :].copy()
                    row_merge["_merge"] = "both"
                    dfr_clean = pd.concat((dfr_clean, row_merge.to_frame().T))
            else:
                row_merge = lo.loc[index, :].copy()
                row_merge["_merge"] = "both"
                dfr_clean = pd.concat((dfr_clean, row_merge.to_frame().T))

        for index, row in ro.iterrows():
            logger.warning("`%s` présent dans `AFFECTATION_LISTING` est ignoré", row_ro["Name"])

        dfr_clean = dfr_clean.drop(["_merge", "fullname_slug", "Name"], axis=1)

        return dfr_clean

    @staticmethod
    def read_target(student_data):
        return pd.read_excel(student_data, engine="openpyxl")


class XlsStudentDataMerge(UVTask):
    """Ajoute toutes les autres informations étudiants

    Ajoute les informations de changement de TD/TP, les tiers-temps et
    des informations par étudiants. Ajoute également les informations
    spécifiées dans ``DOCS``.
    """

    hidden = True
    target_name = "effectif.xlsx"
    target_dir = "."
    unique_uv = False

    def setup(self):
        super().setup()
        self.student_data = XlsStudentData.target_from(**self.info)
        self.target = self.build_target()

        base_dir = os.path.join(self.settings.SEMESTER_DIR, self.uv)
        documents = Documents(base_dir=base_dir)

        if "CHANGEMENT_COURS" in self.settings and self.settings.CHANGEMENT_COURS:
            documents.switch(
                self.settings.CHANGEMENT_COURS,
                colname="Cours",
                backup=True
            )

        if "CHANGEMENT_TD" in self.settings and self.settings.CHANGEMENT_TD:
            documents.switch(
                self.settings.CHANGEMENT_TD,
                colname="TD",
                backup=True
            )

        if "CHANGEMENT_TP" in self.settings and self.settings.CHANGEMENT_TP:
            documents.switch(
                self.settings.CHANGEMENT_TP,
                colname="TP",
                backup=True
            )

        if "TIERS_TEMPS" in self.settings and self.settings.TIERS_TEMPS:
            documents.flag(
                self.settings.TIERS_TEMPS,
                colname="Tiers-temps",
                flags=["Oui", "Non"]
            )

        if "INFO_ETUDIANT" in self.settings and self.settings.INFO_ETUDIANT:
            documents.aggregate_org(
                self.settings.INFO_ETUDIANT,
                colname="Info"
            )

        if "DOCS" in self.settings:
            for action in self.settings.DOCS.actions:
                documents.add_action(action)

        self.documents = documents
        self.file_dep = documents.deps + [self.student_data] + self.settings.config_files

    def get_column_dimensions(self):
        if not os.path.exists(self.target):
            return {}

        def column_dimensions(ws):
            max_column = ws.max_column
            for i in range(1, max_column+1):
                colname = ws.cell(row=1, column=i).value
                width = ws.column_dimensions[get_column_letter(i)].width
                yield colname, width

        wb = load_workbook(self.target)
        ws = wb.active
        return {colname: width for colname, width in column_dimensions(ws)}

    def run(self):
        df = XlsStudentData.read_target(self.student_data)

        # Aggregate documents
        df = self.documents.apply_actions(df, ref_dir=self.settings.CWD)

        dff = sort_values(df, ["Nom", "Prénom"])

        # Get column dimensions of original effectif.xlsx
        column_dimensions = self.get_column_dimensions()

        wb = Workbook()
        ws = wb.active

        for r in dataframe_to_rows(dff, index=False, header=True):
            ws.append(r)

        for cell in ws[1]:
            cell.style = 'Pandas'

        max_column = ws.max_column
        max_row = ws.max_row
        ws.auto_filter.ref = 'A1:{}{}'.format(
            get_column_letter(max_column),
            max_row)

        # On fige la première ligne et les deux premières colonnes
        ws.freeze_panes = "C2"

        # On redimensionne les colonnes d'après la taille précédente
        # ou la taille de l'en-tête
        for cell in ws[1]:
            width = None
            header_value = str(cell.value)

            if header_value in column_dimensions:
                width = column_dimensions[header_value]
            elif header_value == "Nom":
                width = 1.3 * 16
            elif header_value == "Prénom":
                width = 1.3 * 16
            elif header_value:
                width = 1.3 * len(header_value)

            if width is not None:
                ws.column_dimensions[cell.column_letter].width = width

        with Output(self.target) as out:
            wb.save(out.target)

        target = os.path.splitext(self.target)[0] + ".csv"
        with Output(target) as out:
            dff.to_csv(out.target, index=False)

    @staticmethod
    def read_target(student_data_merge):
        return pd.read_excel(student_data_merge, engine="openpyxl")


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
        self.target = self.build_target()

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
        self.target = self.build_target()

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

    .. code:: yaml

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
            if not file_.readline() == "\n":
                raise Exception("Le message doit ")

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

