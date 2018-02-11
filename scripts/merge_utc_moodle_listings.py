#!/usr/bin/env python3

__doc__ = """
Prend en argument un fichier contenant la liste des inscrits telle que
fournie par l'UTC et le convertit en fichier CSV.
"""

import os
import argparse
import pandas as pd
import re

parser = argparse.ArgumentParser()
parser.add_argument('-u', '--utc-list',
                    required=True,
                    type=str,
                    dest='utc_fn',
                    help='Chemin vers le fichier CSV des inscrits')
parser.add_argument('-m', '--moodle-list',
                    required=True,
                    type=str,
                    dest='moodle_fn',
                    help='Chemin vers le fichier CSV des inscrits sur Moodle')
parser.add_argument('-o', '--output-dir', required=False, type=str,
                    dest='output_dir',
                    help='Dossier d\'écriture du fichier CSV')
args = parser.parse_args()

cwd = os.getcwd()
utc_fp = os.path.join(cwd, args.utc_fn)
moodle_fp = os.path.join(cwd, args.moodle_fn)

if args.output_dir:
    output_dir = args.output_dir
else:
    output_dir = cwd

pd.
