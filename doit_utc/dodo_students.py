"""
Fichier qui regroupe des tâches de création d'un fichier Excel sur
l'effectif d'une UV.
"""

import os
import re
import math
import random
import textwrap
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl import utils
from openpyxl.utils.dataframe import dataframe_to_rows

from doit.exceptions import TaskFailed

from .config import settings
from .utils import (
    Output,
    documents,
    generated,
    selected_uv,
    argument,
    parse_args,
    get_unique_uv,
    actionfailed_on_exception,
    taskfailed_on_exception,
    check_columns,
    rel_to_dir,
    slugrot,
    slugrot_string
)
from .tasks import UVTask
from .scripts.parse_utc_list import parse_UTC_listing
from .scripts.add_student_data import (
    add_moodle_data,
    add_UTC_data,
)


class TaskCsvInscrits(UVTask):
    """Construit un fichier CSV à partir des données brutes de la promo
    fournies par l'UTC."""

    target = "inscrits.csv"
    unique_uv = False

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        utc_listing_fn = self.settings.AFFECTATION_LISTING
        self.utc_listing = documents(utc_listing_fn, **self.info)
        self.file_dep = [self.utc_listing]
        self.target = generated(TaskCsvInscrits.target, **self.info)

    def run(self):
        df = parse_UTC_listing(self.utc_listing)
        with Output(self.target) as target:
            df.to_csv(target(), index=False)


class XlsStudentData(UVTask):
    target = "student_data.xlsx"
    unique_uv = False

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.target = generated(XlsStudentData.target, **info)

        kw = {}
        deps = []
        extraction_ENT = documents(self.settings.ENT_LISTING, **info)
        if os.path.exists(extraction_ENT):
            kw["extraction_ENT"] = extraction_ENT
            deps.append(extraction_ENT)

        csv_moodle = documents(self.settings.MOODLE_LISTING, **info)
        if os.path.exists(csv_moodle):
            kw["csv_moodle"] = csv_moodle
            deps.append(csv_moodle)

        csv_UTC = generated(TaskCsvInscrits.target, **info)
        if os.path.exists(csv_UTC):
            kw["csv_UTC"] = csv_UTC
            deps.append(csv_UTC)

        # tiers_temps = documents("tiers_temps.raw", **info)
        # if os.path.exists(tiers_temps):
        #     kw["tiers_temps"] = tiers_temps
        #     deps.append(tiers_temps)

        # TD_switches = documents("TD_switches.raw", **info)
        # if os.path.exists(TD_switches):
        #     kw["TD_switches"] = TD_switches
        #     deps.append(TD_switches)

        # TP_switches = documents("TP_switches.raw", **info)
        # if os.path.exists(TP_switches):
        #     kw["TP_switches"] = TP_switches
        #     deps.append(TP_switches)

        # info_etu = documents("info_étudiants.org", **info)
        # if os.path.exists(info_etu):
        #     kw['info_étudiants'] = info_etu
        #     deps.append(info_etu)

        self.file_dep = deps
        self.kwargs = kw

    def run(self):
        if "extraction_ENT" in self.kwargs:
            print("Chargement de données issues de l'ENT")
            df = pd.read_csv(self.kwargs["extraction_ENT"], sep="\t", encoding='ISO_8859_1')

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

            if "csv_moodle" in self.kwargs:
                df = add_moodle_data(df, self.kwargs["csv_moodle"])

            if "csv_UTC" in self.kwargs:
                df = add_UTC_data(df, self.kwargs["csv_UTC"])
        elif "csv_UTC" in self.kwargs:
            df = pd.read_csv(self.kwargs["csv_UTC"])
            if "csv_moodle" in self.kwargs:
                df = add_moodle_data(df, self.kwargs["csv_moodle"])
        elif "csv_moodle" in self.kwargs:
            fn = self.kwargs["csv_moodle"]
            if fn.endswith('.csv'):
                df = pd.read_csv(fn)
            elif fn.endswith('.xlsx') or fn.endswith('.xls'):
                df = pd.read_excel(fn)

        # if "tiers_temps" in self.kwargs:
        #     df = add_tiers_temps(df, self.kwargs["tiers_temps"])

        # if "TD_switches" in self.kwargs:
        #     df = add_switches(df, self.kwargs["TD_switches"], "TD")

        # if "TP_switches" in self.kwargs:
        #     df = add_switches(df, self.kwargs["TP_switches"], "TP")

        # if "info_étudiants" in self.kwargs:
        #     df = add_student_info(df, self.kwargs["info_étudiants"])

        dff = df.sort_values(["Nom", "Prénom"])

        with Output(self.target) as target:
            dff.to_excel(target(), index=False)


class XlsStudentDataMerge(UVTask):
    """Ajoute toutes les autres informations étudiants"""

    target = "student_data_merge.xlsx"
    unique_uv = False

    def __init__(self, planning, uv, info):
        super().__init__(planning, uv, info)
        self.student_data = generated(XlsStudentData.target, **self.info)
        self.target = generated(XlsStudentDataMerge.target, **self.info)

        # Documents to aggregate
        self.docs = []

        tiers_temps = documents("tiers_temps.raw", **self.info)
        if os.path.exists(tiers_temps):
            self.docs.append((tiers_temps, self.add_tiers_temps))

        TD_switches = documents("TD_switches.raw", **info)
        if os.path.exists(TD_switches):
            self.docs.append((TD_switches, self.add_switches("TD")))

        TP_switches = documents("TP_switches.raw", **info)
        if os.path.exists(TP_switches):
            self.docs.append((TP_switches, self.add_switches("TP")))

        info_etu = documents("info_étudiants.org", **info)
        if os.path.exists(info_etu):
            self.docs.append((info_etu, self.add_student_info))

        agg_docs = (
            self.settings.AGGREGATE_DOCUMENTS
            if "AGGREGATE_DOCUMENTS" in self.settings
            else []
        )
        if isinstance(agg_docs, list):
            self.docs = self.docs + agg_docs
        elif isinstance(agg_docs, dict):
            self.docs = self.docs + [(key, value) for key, value in agg_docs.items()]
        else:
            raise Exception("Format de AGGREGATE_DOCUMENTS incorrect")

        deps = [path for path, _ in self.docs]
        self.file_dep = deps + [self.student_data]

    def run(self):
        df = pd.read_excel(self.student_data)

        for path, aggregater in self.docs:
            if os.path.exists(path):
                print("Aggregating %s" % rel_to_dir(path, settings.BASE_DIR))
                df = aggregater(df, path)
            else:
                print("WARNING: File %s not found!" % rel_to_dir(path, settings.BASE_DIR))

        dff = df.sort_values(["Nom", "Prénom"])

        wb = Workbook()
        ws = wb.active

        for r in dataframe_to_rows(dff, index=False, header=True):
            ws.append(r)

        for cell in ws[1]:
            cell.style = 'Pandas'

        max_column = ws.max_column
        max_row = ws.max_row
        ws.auto_filter.ref = 'A1:{}{}'.format(
            utils.get_column_letter(max_column),
            max_row)

        # On fige la première ligne
        ws.freeze_panes = "A2"

        with Output(self.target) as target0:
            wb.save(target0())

        target = os.path.splitext(self.target)[0] + ".csv"
        with Output(target) as target:
            dff.to_csv(target(), index=False)

    def add_tiers_temps(self, df, fn):
        # Aucun tiers-temps
        df['Tiers-temps'] = False

        # Add column that acts as a primary key
        tf_df = slugrot("Nom", "Prénom")
        df["fullname_slug"] = tf_df(df)

        with open(fn, 'r') as fd:
            for line in fd:
                # Saute commentaire ou ligne vide
                line = line.strip()
                if line.startswith('#'):
                    continue
                if not line:
                    continue

                slugname = slugrot_string(line)

                res = df.loc[df.fullname_slug == slugname]
                if len(res) == 0:
                    raise Exception('Pas de correspondance pour `{:s}`'.format(line))
                elif len(res) > 1:
                    raise Exception('Plusieurs correspondances pour `{:s}`'.format(line))
                df.loc[res.index[0], 'Tiers-temps'] = True

        df = df.drop('fullname_slug', axis=1)
        return df

    def add_switches(self, ctype):
        def add_switches_ctype(df, fn):
            def swap_record(df, idx1, idx2, col):
                tmp = df.loc[idx1, col]
                df.loc[idx1, col] = df.loc[idx2, col]
                df.loc[idx2, col] = tmp

            # Add column that acts as a primary key
            tf_df = slugrot("Nom", "Prénom")
            df["fullname_slug"] = tf_df(df)
            df[f'{ctype}_orig'] = df[ctype]

            with open(fn, 'r') as fd:
                for line in fd:
                    if line.strip().startswith('#'):
                        continue
                    if not line.strip():
                        continue

                    stu1, stu2, *t = [e.strip() for e in line.split('---')]
                    assert len(t) == 0

                    if '@etu' in stu1:
                        stu1row = df.loc[df['Courriel'] == stu1]
                        if len(stu1row) != 1:
                            raise Exception('Nombre d\'enregistrement != 1', len(stu1row), stu1)
                        stu1idx = stu1row.index[0]
                    else:
                        stu1row = df.loc[df.fullname_slug == slugrot_string(stu1)]
                        if len(stu1row) != 1:
                            raise Exception('Nombre d\'enregistrement != 1', len(stu1row), stu1)
                        stu1idx = stu1row.index[0]

                    if re.match('^[TD][0-9]+', stu2):
                        df.loc[stu1idx, ctype] = stu2
                    elif '@etu' in stu2:
                        stu2row = df.loc[df['Courriel'] == stu2]
                        if len(stu2row) != 1:
                            raise Exception('Nombre d\'enregistrement != 1', len(stu2row), stu2)
                        stu2idx = stu2row.index[0]
                        swap_record(df, stu1idx, stu2idx, ctype)
                    else:
                        stu2row = df.loc[df.fullname_slug == slugrot_string(stu2)]
                        if len(stu2row) != 1:
                            raise Exception('Nombre d\'enregistrement != 1', len(stu2row), stu2)
                        stu2idx = stu2row.index[0]
                        swap_record(df, stu1idx, stu2idx, ctype)

            df = df.drop('fullname_slug', axis=1)
            return df

        return add_switches_ctype

    def add_student_info(self, df, fn):
        df['Info'] = ""

        # Add column that acts as a primary key
        tf_df = slugrot("Nom", "Prénom")
        df["fullname_slug"] = tf_df(df)

        infos = open(fn, 'r').read()
        if infos:
            for chunk in re.split("^\\* *", infos, flags=re.MULTILINE):
                if not chunk:
                    continue

                etu, *text = chunk.split("\n", maxsplit=1)
                text = "\n".join(text).strip("\n")
                text = textwrap.dedent(text)
                slugname = slugrot_string(etu)

                res = df.loc[df.fullname_slug == slugname]
                if len(res) == 0:
                    raise Exception('Pas de correspondance pour `{:s}`'.format(etu))
                elif len(res) > 1:
                    raise Exception('Plusieurs correspondances pour `{:s}`'.format(etu))

                df.loc[res.index[0], 'Info'] = text

        df = df.drop('fullname_slug', axis=1)
        return df


@actionfailed_on_exception
def task_csv_exam_groups():
    """Fichier csv des demi-groupe de TP pour le passage des examens de TP."""

    @taskfailed_on_exception
    def csv_exam_groups(target, target_moodle, xls_merge, tp_col, tiers_temps_col):
        df = pd.read_excel(xls_merge)

        def exam_split(df):
            if tiers_temps_col in df.columns:
                dff = df.sort_values(tiers_temps_col, ascending=False)
            else:
                dff = df
            n = len(df.index)
            m = math.ceil(n / 2)
            sg1 = dff.iloc[:m, :][tp_col] + "i"
            sg2 = dff.iloc[m:, :][tp_col] + "ii"
            dff["TPE"] = pd.concat([sg1, sg2])
            return dff

        check_columns(df, [tp_col, tiers_temps_col], file=xls_merge)

        dff = df.groupby(tp_col, group_keys=False).apply(exam_split)
        if 'Adresse de courriel' in dff.columns:
            dff = dff[["Adresse de courriel", "TPE"]]  # Prefer moodle email
        else:
            dff = dff[["Courriel", "TPE"]]

        with Output(target) as target0:
            dff.to_csv(target0(), index=False)

        with Output(target_moodle) as target:
            dff.to_csv(target(), index=False, header=False)

    args = parse_args(
        task_csv_exam_groups,
        argument('-t', '--tiers-temps', required=False, default='Tiers-temps', help="Nom de la colonne des tiers-temps"),
        argument('-p', '--tp', required=False, default='TP', help="Nom de la colonne pour réaliser un groupement"),
    )

    planning, uv, info = get_unique_uv()
    deps = [generated(XlsStudentDataMerge.target, **info)]
    target = generated("exam_groups.csv", **info)
    target_moodle = generated("exam_groups_moodle.csv", **info)

    return {
        "actions": [(csv_exam_groups, [target, target_moodle, deps[0], args.tp, args.tiers_temps])],
        "file_dep": deps,
        "targets": [target_moodle],
        "verbosity": 2,
    }


@actionfailed_on_exception
def task_csv_groups():
    """Fichiers csv des groupes de Cours/TD/TP pour Moodle

Crée des fichiers csv pour chaque UV sélectionnées"""

    @taskfailed_on_exception
    def csv_groups(target, xls_merge, ctype):
        df = pd.read_excel(xls_merge)

        check_columns(df, ctype, file=XlsStudentDataMerge.target)
        dff = df[["Courriel", ctype]]

        with Output(target) as target:
            dff.to_csv(target(), index=False, header=False)

    args = parse_args(
        task_csv_groups,
        argument('-g', '--groups', nargs='*', default=["Cours", "TD", "TP"], help="Liste des groupements à considérer")
    )

    for planning, uv, info in selected_uv():
        deps = [generated(XlsStudentDataMerge.target, **info)]

        for ctype in args.groups:
            target = generated(f"{ctype}_group_moodle.csv", **info)

            yield {
                "name": f"{planning}_{uv}_{ctype}",
                "actions": [(csv_groups, [target, deps[0], ctype])],
                "file_dep": deps,
                "targets": [target],
                "verbosity": 2,
            }


@actionfailed_on_exception
def task_csv_moodle_groups():
    """Fichier csv de sous-groupes (binômes ou trinômes) aléatoires."""

    @taskfailed_on_exception
    def csv_moodle_groups(target, target_moodle, xls_merge, ctype, project, group_names, other_groups):
        df = pd.read_excel(xls_merge)
        check_columns(df, ctype, file=xls_merge)
        gdf = df.groupby(ctype)

        if other_groups is not None:
            if not isinstance(other_groups, list):
                other_groups = [other_groups]

            diff = set(other_groups) - set(df.columns.values)
            if diff:
                s = "s" if len(diff) > 1 else ""
                return TaskFailed(
                    f"Colonne{s} inconnue{s} : `{', '.join(diff)}'; les colonnes sont : {', '.join(df.columns)}"
                )

        # Build list of group names
        if group_names is not None and os.path.exists(group_names):
            with open(group_names, "r") as fd:
                group_names = [l.strip() for l in fd.readlines()]
                shuffle = True
                group_names = [f"%(gn)s_{e}" for e in group_names]
        else:
            shuffle = False
            group_names = [f"%(gn)s_{project}_{e}" for e in list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")]

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
                if etu1["Branche"] == 'GB' and etu2["Branche"] == 'GB':
                    return False

            # Binomes précédents
            if other_groups is not None:
                for gp in other_groups:
                    if etu1[gp] == etu2[gp]:
                        return False

            return True

        def trinome_match(df_group, idx1, idx2, idx3, other_groups=None, foreign=True):
            a = binome_match(df_group, idx1, idx2, other_groups=other_groups, foreign=foreign)
            b = binome_match(df_group, idx1, idx3, other_groups=other_groups, foreign=foreign)
            c = binome_match(df_group, idx2, idx3, other_groups=other_groups, foreign=foreign)
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
                        return trinome_match(df_group, *group, other_groups=other_groups, foreign=foreign)
                    elif len(group) == 2:
                        return binome_match(df_group, *group, other_groups=other_groups, foreign=foreign)
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
                    if not valid_groups(df_group, groups):
                        raise Ooops

                    if len(groups) > len(group_names):
                        raise Exception("Not enough group names")

                    groups_names = group_names[:len(groups)]
                    final_groups = {etu: (gn % dict(gn=gpn)) for gn, group in zip(groups_names, groups) for etu in group}
                except Ooops:
                    continue
                break

            final_df_groups = pd.Series(final_groups, name="group")
            df_group = df_group[["Courriel"]]
            gb = pd.concat((df_group, final_df_groups), axis=1)
            return gb

        df = gdf.apply(add_group, other_groups=other_groups, group_names=group_names)
        df = df.sort_values("group")

        with Output(target) as target0:
            df.to_csv(target0(), index=False)

        with Output(target_moodle) as target:
            df.to_csv(target(), index=False, header=False)

    args = parse_args(
        task_csv_moodle_groups,
        argument('-c', '--course', required=True, help="Nom de colonne pour réaliser un groupement"),
        argument('-p', '--project', required=True, help="Nom du groupement que sera réalisé"),
        argument('-g', '--group-names', required=False, default=None, help="Fichier de noms de groupes"),
        argument('-o', '--other-group', required=False, default=None, help="Nom de colonne d'un autre groupement"),
    )

    planning, uv, info = get_unique_uv()
    xls_merge = generated(XlsStudentDataMerge.target, **info)
    target = generated(f"{args.course}_{args.project}_binomes.csv", **info)
    target_moodle = generated(f"{args.course}_{args.project}_binomes_moodle.csv", **info)
    deps = [xls_merge]

    return {
        "actions": [
            (
                csv_moodle_groups,
                [target, target_moodle, xls_merge, args.course, args.project, args.group_names, args.other_group],
            )
        ],
        "file_dep": deps,
        "targets": [target_moodle],  # target_moodle only to
        # avoid circular dep
    }

@actionfailed_on_exception
def task_csv_groups_groupings():
    """Fichier csv de noms de groupes et groupements à charger sur Moodle.

    Il faut spécifier le nombre de groupes dans chaque groupement et le
    nombre de groupements.
    """

    def csv_groups_groupings(target, ngroups, ngroupings, ngroupsf, ngroupingsf):
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ngroupings = min(26, ngroupings)
        ngroups = min(26, ngroups)

        groups = []
        groupings = []
        for G in range(ngroupings):
            grouping_letter = letters[G]
            grouping_number = str(G + 1)
            grouping = (ngroupingsf
                        .replace("@@", grouping_letter)
                        .replace("##", grouping_number))
            for g in range(ngroups):
                group_letter = letters[g]
                group_number = str(g + 1)
                group = (ngroupsf
                         .replace("@@", grouping_letter)
                         .replace("##", grouping_number)
                         .replace("@", group_letter)
                         .replace("#", group_number))

                groups.append(group)
                groupings.append(grouping)

        df_groups = pd.DataFrame({"groupname": groups, 'groupingname': groupings})
        with Output(target, protected=True) as target:
            df_groups.to_csv(target(), index=False)

    args = parse_args(
        task_csv_groups_groupings,
        argument('-g', type=int, required=True, help="Nombre de groupes dans chaque groupement"),
        argument('-f',
                 default="D##_P1_@",
                 help="Format du nom de groupe (defaut: %(default)s)"),
        argument('-G', type=int, required=True, help="Nombre de groupements"),
        argument('-F',
                 default="D##_P1",
                 help="Format du nom de groupement (defaut: %(default)s)")
    )

    planning, uv, info = get_unique_uv()
    target = generated(f"groups_groupings.csv", **info)

    return {
        "targets": [target],
        "actions": [(csv_groups_groupings,
                     [target, args.g, args.G, args.f, args.F])],
    }

