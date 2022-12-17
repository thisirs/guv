"""
Ce module rassemble les tâches de création d'un fichier Excel central
sur l'effectif d'une UV.
"""

import math
import os
import random
import re

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
from ..helpers import Documents
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
                    rel_to_dir(self.csv_moodle, self.settings.MOODLE_LISTING),
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

        # On réalise la jointure à l'aide de l'adresse email s'il
        # elle est présente
        if "Courriel" not in df.columns:
            raise Exception("La colonne `Courriel` n'est pas présente")

        dfm = pd.merge(
            df,
            df_moodle,
            suffixes=("", "_moodle"),
            how="outer",
            left_on="Courriel",
            right_on="Adresse de courriel",
            indicator=True,
        )

        dfm_both = dfm.loc[dfm["_merge"] == "both"]

        # On affiche la différence symétrique
        lo = dfm.loc[dfm["_merge"] == "left_only"]
        for index, row in lo.iterrows():
            fullname = row["Nom"] + " " + row["Prénom"]
            logger.warning("add_moodle_data: `%s` not in Moodle data", fullname)

        ro = dfm.loc[dfm["_merge"] == "right_only"]
        for index, row in ro.iterrows():
            fullname = row["Nom_moodle"] + " " + row["Prénom_moodle"]
            logger.warning("add_moodle_data: `%s` only in Moodle data", fullname)

        dfm = dfm.drop("_merge", axis=1)
        dfm = dfm.loc[~pd.isnull(dfm.Nom)]

        # On demande à l'utilisateur de réaliser les correspondances
        for index, row in lo.iterrows():
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
                dfm_both = dfm_both.append(row_merge)

        dfm_both = dfm_both.drop("_merge", axis=1)
        return dfm_both

    def add_UTC_data(self, df, fn):
        "Incorpore les données Cours/TD/TP des inscrits UTC"

        if "Nom" not in df.columns:
            raise Exception("Pas de colonnes 'Nom' pour agréger les données")
        if "Prénom" not in df.columns:
            raise Exception("Pas de colonnes 'Prénom' pour agréger les données")

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
                dfr_clean = dfr_clean.append(row_merge)
            else:
                row_merge = lo.loc[index, :].copy()
                row_merge["_merge"] = "both"
                dfr_clean = dfr_clean.append(row_merge)

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
            header_value = cell.value

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


class CsvExamGroups(UVTask, CliArgsMixin):
    """Fichier csv des demi-groupe de TP pour le passage des examens de TP"""

    target_dir = "generated"
    target_name = "exam_groups.csv"
    cli_args = (
        argument(
            "-t",
            "--tiers-temps",
            required=False,
            default="Tiers-temps",
            help="Nom de la colonne des tiers-temps",
        ),
        argument(
            "-p",
            "--tp",
            required=False,
            default="TP",
            help="Nom de la colonne pour réaliser un groupement",
        ),
    )

    def setup(self):
        super().setup()
        self.target = self.build_target()
        target_name = os.path.splitext(self.target_name)[0] + '_moodle.csv'
        self.target_moodle = self.build_target(target_name=target_name)

        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()

    def run(self):
        df = XlsStudentDataMerge.read_target(self.xls_merge)

        def exam_split(df):
            if self.tiers_temps in df.columns:
                dff = df.sort_values(self.tiers_temps, ascending=False)
            else:
                dff = df
            n = len(df.index)
            m = math.ceil(n / 2)
            sg1 = dff.iloc[:m, :][self.tp] + "i"
            sg2 = dff.iloc[m:, :][self.tp] + "ii"
            dff["TPE"] = pd.concat([sg1, sg2])
            return dff

        check_if_present(
            df,
            [self.tp, self.tiers_temps],
            file=self.xls_merge,
            base_dir=self.settings.SEMESTER_DIR,
        )

        dff = df.groupby(self.tp, group_keys=False).apply(exam_split)
        if 'Adresse de courriel' in dff.columns:
            dff = dff[["Adresse de courriel", "TPE"]]  # Prefer moodle email
        else:
            dff = dff[["Courriel", "TPE"]]

        with Output(self.target) as out:
            dff.to_csv(out.target, index=False)

        with Output(self.target_moodle) as out:
            dff.to_csv(out.target, index=False, header=False)


class CsvMoodleGroups(UVTask, CliArgsMixin):
    """Fichier csv de sous-groupes (binômes ou trinômes) aléatoires"""

    target_dir = "generated"
    target_name = "{course}_{project}_binomes.csv"
    cli_args = (
        argument(
            "-c",
            "--course",
            required=True,
            help="Nom de colonne pour réaliser un groupement",
        ),
        argument(
            "-p", "--project", required=True, help="Nom du groupement que sera réalisé"
        ),
        argument(
            "-g",
            "--group-names",
            required=False,
            default=None,
            help="Fichier de noms de groupes",
        ),
        argument(
            "-o",
            "--other-group",
            nargs="+",
            required=False,
            default=None,
            help="Nom de colonne d'un autre groupement",
        ),
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentDataMerge.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target_csv = self.build_target(**self.info)
        self.target_moodle = os.path.splitext(self.target_csv)[0] + '_moodle.csv'

        # target_moodle only to avoid circular dep
        self.target = self.target_moodle

    def run(self):
        df = XlsStudentDataMerge.read_target(self.xls_merge)
        check_if_present(
            df, self.course, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
        )

        if self.other_group is not None:
            if not isinstance(self.other_group, list):
                self.other_groups = [self.other_group]

            diff = set(self.other_group) - set(df.columns.values)
            if diff:
                s = "s" if len(diff) > 1 else ""
                raise Exception(
                    f"Colonne{s} inconnue{s} : `{', '.join(diff)}'; les colonnes sont : {', '.join(df.columns)}"
                )

        # Build list of group names
        if self.group_names is not None and os.path.exists(self.group_names):
            with open(self.group_names, "r") as fd:
                group_names = [l.strip() for l in fd.readlines()]
                shuffle = True
                group_names = [f"%(gn)s_{e}" for e in group_names]
        else:
            shuffle = False
            self.group_names = [
                f"%(gn)s_{self.project}_{e}" for e in list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            ]

        def binome_match(df_group, idx1, idx2, other_groups=None, foreign=True):
            "Renvoie vrai si le binôme est bon"

            etu1 = df_group.loc[idx1]
            etu2 = df_group.loc[idx2]

            if foreign:
                e = [
                    "DIPLOME ETAB ETRANGER SECONDAIRE",
                    "DIPLOME ETAB ETRANGER SUPERIEUR",
                    "AUTRE DIPLOME UNIVERSITAIRE DE 1ER CYCLE HORS DUT",
                ]

                # 2 étrangers == catastrophe
                if (
                    etu1["Dernier diplôme obtenu"] in e
                    and etu2["Dernier diplôme obtenu"] in e
                ):
                    return False

                # 2 GB == catastrophe
                if etu1["Branche"] == "GB" and etu2["Branche"] == "GB":
                    return False

            # Binomes précédents
            if other_groups is not None:
                for gp in other_groups:
                    if etu1[gp] == etu2[gp]:
                        return False

            return True

        def trinome_match(df_group, idx1, idx2, idx3, other_groups=None, foreign=True):
            a = binome_match(
                df_group, idx1, idx2, other_groups=other_groups, foreign=foreign
            )
            b = binome_match(
                df_group, idx1, idx3, other_groups=other_groups, foreign=foreign
            )
            c = binome_match(
                df_group, idx2, idx3, other_groups=other_groups, foreign=foreign
            )

            if other_groups is not None:
                etu1 = df_group.loc[idx1]
                etu2 = df_group.loc[idx2]
                etu3 = df_group.loc[idx3]

                for gp in other_groups:
                    if len(set([etu1[gp], etu2[gp], etu3[gp]])) != 3:
                        return False

            return a or b or c

        class Ooops(Exception):
            pass

        def add_group(df_group, other_groups=None, foreign=True, group_names=None):
            gpn = df_group.name
            index = list(df_group.index)
            if shuffle:
                random.shuffle(group_names)

            def make_random_groups(index, num=3):
                random.shuffle(index)
                num_groups = math.ceil(len(index) / num)
                return np.array_split(index, num_groups)

            def valid_groups(df_group, groups, other_groups=None, foreign=True):
                def valid_group(group):
                    if len(group) == 3:
                        return trinome_match(
                            df_group, *group, other_groups=other_groups, foreign=foreign
                        )
                    elif len(group) == 2:
                        return binome_match(
                            df_group, *group, other_groups=other_groups, foreign=foreign
                        )
                    elif len(group) == 1:
                        return True
                    else:
                        raise Exception("Size of group not supported", len(group))

                for group in groups:
                    if not valid_group(group):
                        return False
                return True

            while True:
                try:
                    groups = make_random_groups(index, num=3)

                    # On vérifie que tous les groupes sont bons
                    if not valid_groups(df_group, groups, other_groups=other_groups):
                        raise Ooops

                    if len(groups) > len(group_names):
                        raise Exception("Not enough group names")

                    groups_names = group_names[: len(groups)]
                    final_groups = {
                        etu: (gn % dict(gn=gpn))
                        for gn, group in zip(groups_names, groups)
                        for etu in group
                    }
                except Ooops:
                    continue
                break

            final_df_groups = pd.Series(final_groups, name="group")
            df_group = df_group[["Courriel"]]
            gb = pd.concat((df_group, final_df_groups), axis=1)
            return gb

        gdf = df.groupby(self.course)
        df = gdf.apply(
            add_group, other_groups=self.other_group, group_names=self.group_names
        )
        df = df.sort_values("group")

        with Output(self.target_csv) as out:
            df.to_csv(out.target, index=False)

        with Output(self.target_moodle) as out:
            df.to_csv(out.target, index=False, header=False)


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
