import os
import re

import numpy as np
import openpyxl
import pandas as pd
from PyPDF2 import PdfReader
from tabula import read_pdf
from unidecode import unidecode

from ..config import settings
from ..exceptions import GuvUserError, ImproperlyConfigured
from ..helpers import Aggregator, Documents, id_slug
from ..logger import logger
from ..openpyxl_patched import fixit
from ..utils import (convert_author, convert_to_time, plural, ps, px,
                     read_dataframe, sort_values)
from ..utils_config import Output, ask_choice, generate_row, rel_to_dir
from .base import SemesterTask, UVTask

fixit(openpyxl)

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows

from ..openpyxl_utils import (fill_row, frame_range, get_range_cells,
                              get_row_cells)


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
                r"^"
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
                r"^(?P<uv>\w+)"
                r"\s+"
                r"(?P<course>[CTD])"
                r"\s*"
                r"(?P<number>[0-9]+)"
                r"\s*"
                r"(?P<week>[AB])?"
            )

        if "RX_JUNK" in self.settings:
            RX_JUNK = re.compile(self.settings.RX_JUNK)
        else:
            RX_JUNK = re.compile(r"\s*(\+-+|\d)\s*")

        with open(self.utc_listing, "r") as fd:
            course_name = course_type = None
            rows = []
            for line in fd:
                line = line.strip()
                if not line:
                    continue

                if (m := RX_UV.match(line)) is not None:
                    number = m.group("number") or ""
                    week = m.group("week") or ""
                    course = m.group("course") or ""
                    course_name = course + number + week
                    course_type = {"C": "Cours", "D": "TD", "T": "TP"}[course]
                    logger.debug("Séance `%s` ajoutée", course_name)
                elif (m := RX_STU.match(line)) is not None:
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
                    logger.debug("Étudiant `%s` ajouté dans `%s`", name, course_name)
                elif (m := RX_JUNK.match(line)) is not None:
                    logger.debug("Line `%s` ignorée", line)
                else:
                    logger.warning("La ligne ci-après n'est pas reconnue :")
                    logger.warning(line.strip())

        df = pd.DataFrame(rows, columns=["Name", "course_type", "course_name", "Branche", "Semestre"])
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
                    choice = ask_choice(
                        f"Semaine pour le créneau {g} (A ou B) ? ",
                        choices={"A": "A", "a": "A", "B": "B", "b": "B"},
                    )
                    rep[g] = g + choice
                df = df.replace({"TP": rep})
        return df

    def run(self):
        if self.utc_listing is None:
            raise ImproperlyConfigured(
                "La variable 'AFFECTATION_LISTING' n'est pas renseignée"
            )
        if not os.path.exists(self.utc_listing):
            raise FileNotFoundError("Le fichier '{0}' n'existe pas".format(
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
                rel_to_dir(self.extraction_ENT),
            )
            if not os.path.isfile(self.extraction_ENT):
                raise FileNotFoundError(
                    "Le chemin `{}` n'existe pas ou n'est pas un fichier".format(
                        rel_to_dir(self.extraction_ENT)
                    )
                )

            df = self.load_ENT_data()

            df_nodup = df.drop_duplicates()

            n = len(df) - len(df_nodup)
            if n > 0:
                df = df_nodup
                logger.warning("Présence de %d enregistrement%s dupliqué%s", n, ps(n), ps(n))

            if self.csv_moodle is not None:
                logger.info(
                    "Ajout des données issues de Moodle: `%s`",
                    rel_to_dir(self.csv_moodle),
                )

                if not os.path.isfile(self.csv_moodle):
                    raise Exception(
                        "Le chemin `{}` n'existe pas ou n'est pas un fichier".format(
                            rel_to_dir(self.csv_moodle)
                        )
                    )

                df_moodle = self.load_moodle_data()
                df = self.add_moodle_data(df, df_moodle)
        else:
            if self.csv_moodle is None:
                raise GuvUserError("Pas de fichier `ENT_LISTING` ni `MOODLE_LISTING`")
            logger.info("Chargement des données issues de Moodle")
            df = self.load_moodle_data()

        if self.csv_UTC is not None:
            logger.info(
                "Ajout des affectations aux Cours/TD/TP : `%s`",
                rel_to_dir(self.csv_UTC),
            )
            df = self.add_UTC_data(df, self.csv_UTC)

        dff = sort_values(df, ["Nom", "Prénom"])

        with Output(self.target) as out:
            dff.to_excel(out.target, index=False)

    def load_ENT_data(self):
        try:
            return self.load_ENT_data_old()
        except (pd.errors.ParserError, KeyError) as e:
            try:
                return self.load_ENT_data_new()
            except KeyError:
                return self.load_ENT_data_basic()

    def load_ENT_data_new(self):
        df = pd.read_excel(self.extraction_ENT)

        # Split information in 2 columns
        df[["Branche", "Semestre"]] = df.pop('Spécialité').str.extract(
            '(?P<Branche>[a-zA-Z]+) *(?P<Semestre>[0-9]+)',
            expand=True
        )
        df["Semestre"] = pd.to_numeric(df['Semestre'])

        # Drop irrelevant columns
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

        # Drop irrelevant columns
        df = df.drop(['Inscription', 'Spécialité 2', 'Résultat ECTS', 'UTC', 'Réussite', 'Statut'], axis=1)

        # Drop unnamed columns
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

        return df

    def load_ENT_data_basic(self):
        return pd.read_excel(self.extraction_ENT)

    def load_moodle_data(self):
        df = read_dataframe(self.csv_moodle)

        # For some reason "Nom" changed to "Nom de famille" in recent Moodle.
        # This breaks the intended clash with "Nom" for effectif.xlsx.
        df = df.rename(columns={"Nom de famille": "Nom"})

        nans = df["Nom"].isna() | df["Prénom"].isna()
        n = sum(nans)
        if n != 0:
            logger.warning(
                "%d enregistrement%s %s été ignoré%s dans le fichier `%s`",
                n,
                ps(n),
                plural(n, "ont", "a"),
                ps(n),
                rel_to_dir(self.csv_moodle)
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
            raise GuvUserError("La colonne `Courriel` n'est pas présente dans le fichier central")

        moodle_short_email = re.match(r"^\w+@", df_moodle.iloc[0]["Adresse de courriel"]) is not None
        ent_short_email = re.match(r"^\w+@", df.iloc[0]["Courriel"]) is not None

        if moodle_short_email ^ ent_short_email:
            logger.info("Les adresses courriels sont dans un format différent, agrégation avec les colonnes `Nom` et `Prénom`")
            left_on = id_slug("Nom", "Prénom")
            right_on = id_slug("Nom", "Prénom")
        else:
            left_on = "Courriel"
            right_on = "Adresse de courriel"

        # Outer aggregation only to handle specifically mismatches
        agg = Aggregator(
            left_df=df,
            right_df=df_moodle,
            left_on=left_on,
            right_on=right_on,
            suffixes=("", "_moodle"),
            how="outer"
        )
        df_outer = agg.merge(clean_exclude="_merge")

        # Warn of any mismatch
        lo = df_outer.loc[df_outer["_merge"] == "left_only"]
        for index, row in lo.iterrows():
            fullname = row["Nom"] + " " + row["Prénom"]
            logger.warning("`%s` n'est pas présent dans les données Moodle", fullname)

        ro = df_outer.loc[df_outer["_merge"] == "right_only"]
        for index, row in ro.iterrows():
            fullname = row["Nom_moodle"] + " " + row["Prénom_moodle"]
            logger.warning("`%s` n'est pas présent dans le fichier central", fullname)

        # Base dataframe to add row to
        df_both = df_outer.loc[df_outer["_merge"] == "both"]

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

        return df_both.drop(["_merge"], axis=1)

    def add_UTC_data(self, df, fn):
        "Incorpore les données Cours/TD/TP des inscrits UTC"

        if "Nom" not in df.columns:
            raise GuvUserError("Pas de colonne 'Nom' pour agréger les données")
        if "Prénom" not in df.columns:
            raise GuvUserError("Pas de colonne 'Prénom' pour agréger les données")

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
            logger.warning("`%s` présent dans `AFFECTATION_LISTING` est ignoré", row["Name"])

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
        documents = Documents(base_dir=base_dir, info=self.info)

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

        # Write set of columns for completion
        fp = os.path.join(self.settings.SEMESTER_DIR, self.uv, "generated", ".columns.list")
        with open(fp, "w") as file:
            file.write("\n".join(f"{e}" for e in df.columns.values))

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
                width = 1.3 * max(len(header_value), 4)

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


class UtcUvListToCsv(SemesterTask):
    """Crée un fichier CSV des créneaux de toutes les UVs à partir du PDF"""

    hidden = True
    target_dir = "documents"
    target_name = "UTC_UV_list.csv"

    def setup(self):
        super().setup()

        self.target = self.build_target()

        if "CRENEAU_UV" in self.settings:
            self.uv_list_filename = os.path.join(
                self.settings.SEMESTER_DIR,
                self.settings.CRENEAU_UV
            )
        else:
            self.uv_list_filename = None

        if self.uv_list_filename is not None:
            self.file_dep = [self.uv_list_filename]
        else:
            self.file_dep = []

    def read_pdf(self):
        pdf = PdfReader(open(self.uv_list_filename, 'rb'))
        npages = len(pdf.pages)

        possible_cols = ['Code enseig.', 'Activité', 'Jour', 'Heure début',
                         'Heure fin', 'Semaine', 'Locaux', 'Type créneau',
                         'Lib. créneau', 'Responsable enseig.']

        tables = []
        pdo = {"header": None}
        for i in range(npages):
            logger.info("Processing page (%d/%d)", i+1, npages)
            page = i + 1
            tabula_args = {'pages': page}
            # Use pdo.copy(): pdo is changed by read_pdf
            df = read_pdf(self.uv_list_filename, **tabula_args, pandas_options=pdo.copy())[0]

            if page == 1:
                # Detect header (might be a two-line header)
                header_height = ((re.match('[A-Z]{,3}[0-9]+', str(df.iloc[0, 0])) is None) +
                                 (re.match('[A-Z]{,3}[0-9]+', str(df.iloc[1, 0])) is None))
                if header_height == 0:
                    raise GuvUserError("No header detected")
                logger.info("Detected header has %d lines", header_height)

                # Compute single line/multiline header
                header = df.iloc[:header_height].fillna('').agg(['sum']).iloc[0]
                logger.info("Header is: %s", ' '.join(header))

                # Extract real data
                df = df.iloc[header_height:]

                # Set name of columns from header
                df = df.rename(columns=header)

                # Rename incorrectly parsed headers
                df = df.rename(columns={
                    'Activit': 'Activité',
                    'Type cr neau': 'Type créneau',
                    'Lib. cr': 'Lib. créneau',
                    'Lib.créneau': 'Lib. créneau',
                    'Lib.': 'Lib. créneau',
                    'Lib.\rcréneau': 'Lib. créneau',
                    'Heuredébut': 'Heure début',
                    'Heure d': 'Heure début',
                    'Heure déb': 'Heure début',
                    'Hteure fin': 'Heure fin',
                    'Heurefin': 'Heure fin',
                    'Locaux hybrides': "Locaux"
                })

                unknown_cols = list(set(df.columns) - set(possible_cols))
                if unknown_cols:
                    raise GuvUserError("Colonnes inconnues détectées:", ", ".join(unknown_cols))

                # Get list of detected columns
                cols = df.columns.to_list()

                # 'Semaine' is the only column that might not be
                # detected in next pages because it can be empty.
                # Store its index to insert a blank column if needed
                if "Semaine" in cols:
                    week_idx = cols.index('Semaine')
                else:
                    week_idx = cols.index('Heure fin') + 1

                logger.info("%d columns found", len(df.columns))
                logger.info(" ".join(df.columns))
            else:
                logger.info("%d columns found", len(df.columns))

                # Semaine column might be empty and not detected
                if len(df.columns) == len(cols):
                    pass
                elif len(df.columns) == len(cols) - 1:
                    df.insert(week_idx, 'Semaine', np.nan)
                else:
                    raise GuvUserError("Mauvais nombre de colonnes détectées")
                df.columns = cols

                # Detect possible multiline header
                header_height = ((re.match('[A-Z]{,3}[0-9]+', str(df.iloc[0, 0])) is None) +
                                 (re.match('[A-Z]{,3}[0-9]+', str(df.iloc[1, 0])) is None))
                logger.info("Header has %d lines", header_height)
                df = df.iloc[header_height:]

            tables.append(df)

        df = pd.concat(tables)
        useful_cols = [
            "Code enseig.",
            "Activité",
            "Jour",
            "Heure début",
            "Heure fin",
            "Semaine",
            "Locaux",
            "Lib. créneau",
        ]
        df = df[useful_cols]

        return df

    def run(self):
        if self.uv_list_filename is None:
            raise ImproperlyConfigured("La variable `CRENEAU_UV` doit être définie")

        # Lire tous les créneaux par semaine de toutes les UVs
        if not os.path.exists(self.uv_list_filename):
            uv_fn = rel_to_dir(self.uv_list_filename, self.settings.SEMESTER_DIR)
            raise FileNotFoundError(f"Le fichier n'existe pas: {uv_fn}")

        df = self.read_pdf()

        # Remove duplicate indexes from concat
        df.reset_index(drop=True, inplace=True)

        # T1 instead of T 1
        df['Lib. créneau'] = df['Lib. créneau'].replace(' +', '', regex=True)

        # A ou B au lieu de semaine A et semaine B
        df['Semaine'] = df['Semaine'].replace("^semaine ([AB])$", "\\1", regex=True)

        # Semaine ni A ni B pour les TP: demander
        uvs = self.settings.UVS

        def fix_semaineAB(group):
            if group.name[1] == 'TP' and len(group.index) > 1:
                nans = group.loc[(pd.isnull(group['Semaine']))]
                if 0 < len(nans.index) or len(nans.index) < len(group.index):
                    if group.name[0] in uvs:
                        for index, row in nans.iterrows():
                            choice = ask_choice(
                                f'Semaine pour le créneau {row["Lib. créneau"]} de TP de {group.name[0]} (A ou B) ? ',
                                choices={"A": "A", "a": "A", "B": "B", "b": "B"},
                            )
                            group.loc[index, "Semaine"] = choice
                    else:
                        group.loc[nans.index, 'Semaine'] = 'A'
                return group
            else:
                return group

        df = df.groupby(['Code enseig.', 'Activité'], group_keys=False).apply(fix_semaineAB)

        with Output(self.target) as out:
            df.to_csv(out.target, index=False)


class WeekSlotsAll(SemesterTask):
    """Rassemble les fichiers ``planning_hebdomadaire.xlsx`` de chaque UV/UE.

    Les colonnes sont :

    - Planning
    - Code enseig.
    - Jour
    - Heure début
    - Heure fin
    - Locaux
    - Semaine
    - Lib. créneau
    - Intervenants
    - Abbrev
    - Responsable

    """

    hidden = True
    target_dir = "generated"
    target_name = "planning_hebdomadaire.xlsx"

    def setup(self):
        super().setup()
        self.target = self.build_target()
        self.affectations = [
            (planning, uv, WeekSlots.target_from(**info))
            for planning, uv, info in self.selected_uv()
        ]
        self.file_dep = [f for _, _, f in self.affectations]

    def run(self):
        def func(planning, uv, xls_aff):
            df = WeekSlots.read_target(xls_aff)
            df.insert(0, "Code enseig.", uv)
            df.insert(0, "Planning", planning)
            return df

        df_affs = [func(planning, uv, xls_aff) for planning, uv, xls_aff in self.affectations]
        df_aff = pd.concat(df_affs, ignore_index=True)
        df_aff.Semaine = df_aff.Semaine.astype(object)

        with Output(self.target) as out:
            df_aff.to_excel(out.target, index=False)

    @staticmethod
    def read_target(week_slots_all):
        df = pd.read_excel(week_slots_all, engine="openpyxl")

        df["Heure début"] = df["Heure début"].apply(convert_to_time)
        df["Heure fin"] = df["Heure fin"].apply(convert_to_time)

        return df


class PlanningSlotsAll(SemesterTask):
    """Rassemble les fichiers `plannings.xlsx` de chaque UE/UV."""

    hidden = True
    unique_uv = False
    target_dir = "generated"
    target_name = "planning_all.xlsx"

    def setup(self):
        super().setup()
        self.target = self.build_target()
        self.planning_slots_files = [
            (planning, uv, PlanningSlots.target_from(**info))
            for planning, uv, info in self.selected_uv()
        ]
        self.file_dep = [f for _, _, f in self.planning_slots_files]

    def run(self):
        def func(planning, uv, xls_aff):
            df = PlanningSlots.read_target(xls_aff)
            df.insert(0, "Code enseig.", uv)
            df.insert(0, "Planning", planning)
            return df

        dfs = [
            func(planning, uv, xls_aff)
            for planning, uv, xls_aff in self.planning_slots_files
        ]

        df = pd.concat(dfs, ignore_index=True)
        df.Semaine = df.Semaine.astype(object)

        with Output(self.target) as out:
            df.to_excel(out.target, index=False)

    @staticmethod
    def read_target(planning_slots_all):
        df = pd.read_excel(planning_slots_all, engine="openpyxl")

        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["Heure début"] = df["Heure début"].apply(convert_to_time)
        df["Heure fin"] = df["Heure fin"].apply(convert_to_time)

        return df


class Planning(SemesterTask):
    """Fichier csv de tous les jours composant le ou les plannings du semestre."""

    hidden = True
    target_name = "planning_{planning}.csv"
    target_dir = "generated"

    def setup(self):
        super().setup()
        self.target = self.build_target()

        self.targets = [
            self.build_target(planning=planning)
            for planning in self.settings.PLANNINGS
        ]

        # Set uptodate value without raising Exception or displaying warnings
        self.uptodate = {"plannings": ", ".join(self.settings.PLANNINGS)}
        for planning in self.settings.PLANNINGS:
            props = self.settings.PLANNINGS[planning]

            for name in ["PL_BEG", "PL_END", "TURN", "SKIP_DAYS_C", "SKIP_DAYS_D", "SKIP_DAYS_T"]:
                try:
                    if name in props:
                        value = props[name]
                    else:
                        value = self.settings[name]
                    self.uptodate[planning + "_" + name.lower()] = value
                except ImproperlyConfigured:
                    self.uptodate[planning + "_" + name.lower()] = None

    def run(self):
        for planning in self.settings.PLANNINGS:
            props = self.settings.PLANNINGS[planning]

            for name in ["PL_BEG", "PL_END", "TURN", "SKIP_DAYS_C", "SKIP_DAYS_D", "SKIP_DAYS_T"]:
                if name not in props:
                    logger.info(
                        f"La clé `{name}` est absente du planning `{planning}` dans la "
                        f"variable `PLANNINGS`, utilisation de la variable globale `{name}`."
                    )
                    props[name] = self.settings[name]

            pl_beg = props["PL_BEG"]
            pl_end = props["PL_END"]
            skip_days_c = props["SKIP_DAYS_C"]
            skip_days_d = props["SKIP_DAYS_D"]
            skip_days_t = props["SKIP_DAYS_T"]
            turn = props["TURN"]

            for d in skip_days_c:
                if d < pl_beg or d > pl_end:
                    logger.warning("Le jour %s renseigné dans `SKIP_DAYS_C` ne fait pas partie du planning", d)

            for d in skip_days_d:
                if d < pl_beg or d > pl_end:
                    logger.warning("Le jour %s renseigné dans `SKIP_DAYS_D` ne fait pas partie du planning", d)

            for d in skip_days_t:
                if d < pl_beg or d > pl_end:
                    logger.warning("Le jour %s renseigné dans `SKIP_DAYS_T` ne fait pas partie du planning", d)

            for d in turn:
                if d < pl_beg or d > pl_end:
                    logger.warning("Le jour %s renseigné dans `TURN` ne fait pas partie du planning", d)

            # DataFrame of days in planning
            planning_C = pd.DataFrame(
                generate_row(pl_beg, pl_end, skip_days_c, turn),
                columns=["date", "Jour", "num", "Semaine", "numAB", "nweek"],
            )
            planning_D = pd.DataFrame(
                generate_row(pl_beg, pl_end, skip_days_d, turn),
                columns=["date", "Jour", "num", "Semaine", "numAB", "nweek"],
            )
            planning_T = pd.DataFrame(
                generate_row(pl_beg, pl_end, skip_days_t, turn),
                columns=["date", "Jour", "num", "Semaine", "numAB", "nweek"],
            )

            for plng, text, number in (
                    (planning_C, "cours", 14),
                    (planning_D, "TD", 13),
                    (planning_T, "TP", 14),
            ):
                counts = plng["Jour"].value_counts()
                unique = counts.unique()
                if len(unique) != 1:
                    serie = ", ".join(f"{index} : {value}" for index, value in counts.items())
                    logger.warning("Le nombre de semaines de %s n'est pas le même pour tous les jours : %s", text, serie)
                elif unique.item() != number:
                    logger.warning("Le nombre de semaines de %s est différent de %d : %d", text, number, unique.item())

            planning_C["Activité"] = "Cours"
            planning_D["Activité"] = "TD"
            planning_T["Activité"] = "TP"
            df = pd.concat((planning_C, planning_D, planning_T))

            with Output(self.target.format(planning=planning)) as out:
                df.to_csv(out.target, index=False)


class PlanningSlots(UVTask):
    """Fichier Excel des créneaux sur le planning entier.

    Les colonnes du fichier sont :

    - Code enseig.: SY02
    - Activité: TP
    - Jour: Lundi
    - Heure début: 14:15
    - Heure fin: 16:15
    - Semaine: B
    - Locaux: BF B 113
    - Lib. créneau: T1
    - Planning: P2021
    - Responsable:
    - Intervenants: Fisher
    - Responsable:
    - date: 2021-03-08
    - num: 1
    - numAB: 1
    - nweek: 4

"""

    hidden = True
    unique_uv = False
    target_name = "planning.xlsx"
    target_dir = "generated"

    def setup(self):
        super().setup()
        self.target = self.build_target()

        self.week_slots = WeekSlots.target_from(**self.info)
        self.planning = Planning.target_from(**self.info)
        self.file_dep = [self.week_slots, self.planning]

    def run(self):
        # Load all days in the planning with "Activité" being either "Cours",
        # "TD", "TP"
        planning = pd.read_csv(self.planning)

        # Load week slots and rename "Activité" column that need not be "Cours",
        # "TD", "TP" only.
        df = WeekSlots.read_target(self.week_slots)
        df = df.rename(columns={"Activité": "Activité alt"})
        mask_C = df["Activité alt"] == "Cours"
        mask_D = df["Activité alt"] == "TD"
        mask_T = df["Activité alt"] == "TP"

        # Separate based on "Activité alt"
        df_C = df.loc[mask_C]
        df_D = df.loc[mask_D]
        df_T = df.loc[mask_T]

        # Handle where "Activité alt" is not "Cours", "TD" or "TP" in week slots
        df_other = df.loc[~(mask_C | mask_D | mask_T)]
        if len(df_other) > 0:
            for name, group in df_other.groupby("Activité alt"):
                logger.warning(
                    "%d créneau%s %s étiqueté%s `%s`, le%s compter comme `Cours`, `TD` ou `TP` ?",
                    len(df_other),
                    px(len(df_other)),
                    plural(len(df_other), "sont", "est"),
                    ps(len(df_other)),
                    name,
                    ps(len(df_other)),
                )
                result = ask_choice("Choix ? ", {"Cours": "Cours", "TD": "TD", "TP": "TP"})
                if result == "Cours":
                    df_C = pd.concat((df_C, df_other))
                elif result == "TD":
                    df_D = pd.concat((df_D, df_other))
                elif result == "TP":
                    df_T = pd.concat((df_T, df_other))
                else:
                    raise RuntimeError("Logical error")

        planning_noweek = planning.drop("Semaine", axis=1)

        planning_noweek_Cours = planning_noweek.loc[planning_noweek["Activité"] == "Cours"]
        df_Cp = pd.merge(df_C, planning_noweek_Cours, how="left", on="Jour")

        planning_noweek_TD = planning_noweek.loc[planning_noweek["Activité"] == "TD"]
        df_Dp = pd.merge(df_D, planning_noweek_TD, how="left", on="Jour")

        if df_T["Semaine"].hasnans:
            planning_noweek_TP = planning_noweek.loc[planning_noweek["Activité"] == "TP"]
            df_Tp = pd.merge(df_T, planning_noweek_TP, how="left", on="Jour")
        else:
            planning_TP = planning.loc[planning_noweek["Activité"] == "TP"]
            df_Tp = pd.merge(df_T, planning_TP, how="left", on=["Jour", "Semaine"])

        dfp = pd.concat([df_Cp, df_Dp, df_Tp], ignore_index=True)

        with Output(self.target) as out:
            dfp.to_excel(out.target, index=False)

    @staticmethod
    def read_target(planning_slots):
        df = pd.read_excel(planning_slots, engine="openpyxl")

        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["Heure début"] = df["Heure début"].apply(convert_to_time)
        df["Heure fin"] = df["Heure fin"].apply(convert_to_time)

        return df


class WeekSlots(UVTask):
    """Fichier Excel des créneaux hebdomadaires d'une UV.

    Crée un fichier "planning_hebdomadaire.xlsx" dans chaque dossier
    d'UV/UE. Le fichier est prérempli d'après le fichier pdf des
    créneaux de toutes les UVs. Si l'UV/UE n'est pas trouvée, un
    fichier avec en-tête mais sans créneau est créé.

    """

    hidden = True
    unique_uv = False
    target_name = "planning_hebdomadaire.xlsx"
    target_dir = "documents"

    def setup(self):
        super().setup()
        self.target = self.build_target()
        self.uvlist_csv = UtcUvListToCsv.target_from()
        self.file_dep = [self.uvlist_csv]

    def run(self):
        df = pd.read_csv(self.uvlist_csv)
        self.df_uv = df.loc[df["Code enseig."] == self.uv, :]

        output_obj = self.create_excel_file()
        if output_obj.action not in ["abort", "keep"]:
            workbook = load_workbook(filename=self.target)
            self.add_second_worksheet(workbook)

    @staticmethod
    def read_target(week_slots):
        df = pd.read_excel(week_slots, engine="openpyxl", dtype={
            "Activité": str,
            "Jour": str,
            "Heure début": str,
            "Heure fin": str,
            "Semaine": str,
            "Locaux": str,
            "Lib. créneau": str,
            "Intervenants": str,
            "Abbrev": str,
            "Responsable": str
        })
        if len(df.index) == 0:
            fn = rel_to_dir(week_slots)
            logger.warning(f"Le fichier `{fn}` est vide")

        if df["Activité"].isnull().any():
            fn = rel_to_dir(week_slots)
            raise GuvUserError(f"La colonne `Activité` du fichier `{fn}` ne doit pas contenir d'élément vide.")

        rest = set(df["Activité"]) - set(["Cours", "TD", "TP"])
        if rest:
            rest_msg = ", ".join(f"`{e}`" for e in rest)
            fn = rel_to_dir(week_slots)
            logger.warning("La colonne `Activité` du fichier `%s` contient des libellés non standards (`Cours`, `TD` et `TP`) : %s", fn, rest_msg)

        if df["Jour"].isnull().any():
            fn = rel_to_dir(week_slots)
            raise GuvUserError(f"La colonne `Jour` du fichier `{fn}` ne doit pas contenir d'élément vide.")

        rest = set(df["Jour"]) - set(["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"])
        if rest:
            rest_msg = ", ".join(f"`{e}`" for e in rest)
            fn = rel_to_dir(week_slots)
            raise GuvUserError(f"La colonne `Jour` du fichier `{fn}` ne doit contenir que des jours de la semaine, elle contient {rest_msg}")

        if df["Lib. créneau"].isnull().any():
            fn = rel_to_dir(week_slots)
            raise GuvUserError(f"La colonne `Lib. créneau` du fichier `{fn}` ne doit pas contenir d'élément vide.")

        df["Heure début"] = df["Heure début"].apply(convert_to_time)
        df["Heure fin"] = df["Heure fin"].apply(convert_to_time)

        # Populate "Abbrev" column where possible
        empty = df["Abbrev"].isna() & ~df["Intervenants"].isna()
        df.loc[empty, "Abbrev"] = df.loc[empty, "Intervenants"].apply(convert_author)

        # Warn if abbrev clashes
        for index, group in df.groupby("Abbrev"):
            insts = group["Intervenants"].dropna().unique()
            if len(insts) > 1:
                insts_list = ", ".join(insts)
                fn = rel_to_dir(week_slots)
                logger.warning(f"Les intervenants suivants ont les mêmes initiales : {insts_list}. "
                               f"Modifier la colonne `Abbrev` dans le fichier `{fn}`.")

        return df

    def create_excel_file(self):
        df = pd.read_csv(self.uvlist_csv)
        self.df_uv = df.loc[df["Code enseig."] == self.uv, :]

        # Test if UV/UE is in listing from UtcUvListToCsv
        if len(self.df_uv) == 0:
            creneau_uv = rel_to_dir(self.settings.CRENEAU_UV)
            logger.warning(
                "L'UV/UE `%s` n'existe pas dans le fichier `%s`, "
                "un fichier Excel sans créneau est créé.",
                self.uv,
                creneau_uv
            )
            columns = [
                "Activité",
                "Jour",
                "Heure début",
                "Heure fin",
                "Locaux",
                "Semaine",
                "Lib. créneau",
                "Intervenants",
                "Abbrev",
                "Responsable",
            ]
            self.df_uv = pd.DataFrame(columns=columns)
        else:
            self.df_uv = self.df_uv.sort_values(["Lib. créneau", "Semaine"])
            self.df_uv = self.df_uv.drop(["Code enseig."], axis=1)
            self.df_uv["Intervenants"] = np.nan
            self.df_uv["Abbrev"] = np.nan
            self.df_uv["Responsable"] = np.nan

        # Write to disk
        with Output(self.target, protected=True) as out:
            self.df_uv.to_excel(out.target, sheet_name="Intervenants", index=False)

        # Return decision in Output
        return out

    def add_second_worksheet(self, workbook):
        worksheet = workbook.create_sheet("Décompte des heures")

        # Make current worksheet the default one, useful for get_address_of_cell
        workbook.active = worksheet

        ref = worksheet.cell(1, 1)
        num_record = len(self.df_uv)
        if num_record == 0:
            num_record = 10

        semAB = not self.df_uv.loc[self.df_uv["Activité"] == "TP", "Semaine"].isna().all()
        has_TP = "TP" in self.df_uv["Activité"].values

        keywords = [
            "Intervenants",
            "Statut",
            "Cours",
            "TD",
            "TP",
            "Heures Cours prév",
            "Heures TD prév",
            "Heures TP prév",
            "UTP",
            "Heure équivalent TD",
            "Heure brute"
        ]

        if not has_TP:
            del keywords[keywords.index("Statut")]
            del keywords[keywords.index("TP")]
            del keywords[keywords.index("Heures TP prév")]

        # Write header
        row_cells = get_row_cells(ref, 0, *keywords)
        headers = {e: e for e in keywords}
        if has_TP and semAB:
            headers["TP"] = "TP A/B"
        fill_row(row_cells, **headers)
        for cell in row_cells.values():
            cell.style = "Pandas"

        # Write rows
        for i in range(num_record):
            row_cells = get_row_cells(ref, i+1, *keywords)
            elts = {
                "Heures Cours prév": lambda row: "=2*16*{}".format(row["Cours"].coordinate),
                "Heures TD prév": lambda row: "=2*16*{}".format(row["TD"].coordinate),
                "Heure équivalent TD": lambda row: "=2/3*{}".format(row["UTP"].coordinate),
            }

            if has_TP:
                elts["Heures TP prév"] = lambda row: "=2*{num_week}*{TP_cell}".format(
                    TP_cell=row["TP"].coordinate,
                    num_week="8" if semAB else "16"
                )
                elts["UTP"] = lambda row: "=2*16*2.25*{cours_cell}+2*16*1.5*{TD_cell}+2*{num_week}*{TP_cell}*{status_cell}".format(
                    cours_cell=row["Cours"].coordinate,
                    TD_cell=row["TD"].coordinate,
                    TP_cell=row["TP"].coordinate,
                    status_cell=row["Statut"].coordinate,
                    num_week="8" if semAB else "16"
                )
                elts["Heure brute"] = lambda row: "=2*16*{cours_cell}+2*16*{TD_cell}+2*{num_week}*{TP_cell}".format(
                    cours_cell=row["Cours"].coordinate,
                    TD_cell=row["TD"].coordinate,
                    TP_cell=row["TP"].coordinate,
                    num_week="8" if semAB else "16"
                )
                elts["Statut"] = 1.5
            else:
                elts["UTP"] = lambda row: "=2*16*2.25*{cours_cell}+2*16*1.5*{TD_cell}".format(
                    cours_cell=row["Cours"].coordinate,
                    TD_cell=row["TD"].coordinate,
                )
                elts["Heure brute"] = lambda row: "=2*16*{cours_cell}+2*16*{TD_cell}".format(
                    cours_cell=row["Cours"].coordinate,
                    TD_cell=row["TD"].coordinate,
                )

            fill_row(row_cells, **elts)

        frame_range(ref, row_cells[keywords[-1]])

        # Write real
        row_cells = get_row_cells(ref, num_record+1, *keywords)
        range_cells = get_range_cells(ref.below(), num_record-1, *keywords)
        row_cells["Cours"].value = "=SUM({})".format(range_cells["Cours"])
        row_cells["TD"].value = "=SUM({})".format(range_cells["TD"])
        if has_TP:
            row_cells["TP"].value = "=SUM({})".format(range_cells["TP"])
        row_cells["Cours"].left().text("Total")

        # Write expected
        n_cours = len(self.df_uv.loc[self.df_uv["Activité"] == "Cours"])
        n_TD = len(self.df_uv.loc[self.df_uv["Activité"] == "TD"])

        row_cells = get_row_cells(ref, num_record+2, *keywords)
        row_cells["Cours"].value = n_cours
        row_cells["TD"].value = n_TD
        if has_TP:
            n_TP = len(self.df_uv.loc[self.df_uv["Activité"] == "TP"])
            row_cells["TP"].value = n_TP
        row_cells["Cours"].left().text("Attendu")

        workbook.save(self.target)
