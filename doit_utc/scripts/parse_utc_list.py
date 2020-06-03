#!/usr/bin/env python3

__doc__ = """
Prend en argument un fichier contenant la liste des inscrits telle que
fournie par l'UTC et le convertit en fichier CSV.
"""

import os
import re
import math
import pandas as pd


def parse_UTC_listing(filename):
    """Parse FILENAME into DataFrame"""

    RX_STU = re.compile(r"^\s*\d{3}\s{3}(.{23})\s{3}([A-Z]{2})([0-9]{2})$")
    RX_UV = re.compile(
        r"^\s*(?P<uv>\w+)\s+(?P<course>[CTD])\s*(?P<number>[0-9]+)\s*(?P<week>[AB])?"
    )

    with open(filename, "r") as fd:
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
                    name = m.group(1).strip()
                    spe = m.group(2)
                    sem = int(m.group(3))
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

    df = pd.DataFrame(rows)
    df = pd.pivot_table(
        df,
        columns=["course_type"],
        index=["Name", "Branche", "Semestre"],
        values="course_name",
        aggfunc="first",
    )
    df = df.reset_index()

    # Il peut arriver qu'un créneaux A/B ne soit pas marqué comme tel
    # car il n'a pas de pendant pour l'autre semaine. On le fixe donc
    # manuellement à A ou B.
    if "TP" in df.columns:
        semAB = [i for i in df.TP.unique() if re.match("T[0-9]{,2}[AB]")]
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


def add_exam_split(df):
    def exam_split(df):
        n = len(df.index)
        m = math.ceil(n / 2)

        sg1 = df.iloc[:m, :]["TP"] + "i"
        sg2 = df.iloc[m:, :]["TP"] + "ii"
        return pd.DataFrame({"TPE": pd.concat([sg1, sg2])})

    # df.groupby('TP').sort_values('Tiers-temps').apply(exam_split)
    dff = df.groupby("TP", group_keys=False).apply(exam_split)
    return pd.concat([df, dff], axis=1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-u",
        "--utc-list",
        required=True,
        type=str,
        dest="utc_fn",
        help="Chemin vers le fichier des inscrits",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        required=False,
        type=str,
        dest="output_dir",
        help="Dossier/fichier d'écriture du fichier CSV",
    )
    args = parser.parse_args()

    cwd = os.getcwd()
    utc_fp = os.path.join(cwd, args.utc_fn)

    outdir = os.path.join(cwd, args.output_dir)

    if os.path.isfile(outdir):
        raise Exception("File exists")
    elif os.path.isdir(outdir):
        out = os.path.join(outdir, "out.csv")
    else:
        out = outdir

    df = parse_UTC_listing(utc_fp)
    df.to_csv(out)
