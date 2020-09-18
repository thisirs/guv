#!/usr/bin/env python3

__doc__ = """
Prend en argument un fichier contenant la liste des inscrits telle que
fournie par l'UTC et le convertit en fichier CSV.
"""

import os
import re
import math
import pandas as pd


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
