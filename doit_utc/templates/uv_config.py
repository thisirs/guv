"""Fichier de configuration de l'UV"""


import os
from doit_utc.utils import aggregate

# Don't catch exception to see backtrace
# DEBUG = 1

UV_DIR = os.path.dirname(__file__)


# List of UV to iterate on by default
SELECTED_UVS = [os.path.basename(os.path.dirname(__file__))]

def document(filename):
    return os.path.join(UV_DIR, "documents", filename)


def generated(filename):
    return os.path.join(UV_DIR, "generated", filename)

# Chemin relatif vers le listing provenant de Moodle
MOODLE_LISTING = document("SY02 Notes.xlsx")

# Listing issu de l'ENT
ENT_LISTING = document("extraction_enseig_note.XLS")

# Listing fourni par
AFFECTATION_LISTING = document("inscrits_boufflet.txt")

# Documents supplémentaires à agréger au fichier Excel
AGGREGATE_DOCUMENTS = {
    generated("final_groups.csv"): aggregate(
        left_on="Courriel",
        right_on="Courriel",
        kw_read={"names": ["Courriel", "group"]}
    )
}


# Identifiant Moodle des différents groupes créés sur la page SY02
GROUP_ID = {
    'C1': 5377,
    'C2': 5378,
    'D1': 5379,
    'D10': 5388,
    'D11': 5389,
    'D12': 5390,
    'D2': 5380,
    'D3': 5381,
    'D4': 5382,
    'D5': 5383,
    'D6': 5384,
    'D7': 5385,
    'D8': 5386,
    'D9': 5387,
    'T1A': 5359,
    'T1Ai': 5391,
    'T1Aii': 5397,
    'T1B': 5371,
    'T1Bi': 5403,
    'T1Bii': 5409,
    'T2A': 5360,
    'T2Ai': 5392,
    'T2Aii': 5398,
    'T2B': 5372,
    'T2Bi': 5404,
    'T2Bii': 5410,
    'T3A': 5361,
    'T3Ai': 5393,
    'T3Aii': 5399,
    'T3B': 5373,
    'T3Bi': 5405,
    'T3Bii': 5411,
    'T4A': 5362,
    'T4Ai': 5394,
    'T4Aii': 5400,
    'T4B': 5374,
    'T4Bi': 5406,
    'T4Bii': 5412,
    'T5A': 5363,
    'T5Ai': 5395,
    'T5Aii': 5401,
    'T5B': 5375,
    'T5Bi': 5407,
    'T5Bii': 5413,
    'T6A': 5364,
    'T6Ai': 5396,
    'T6Aii': 5402,
    'T6B': 5376,
    'T6Bi': 5408,
    'T6Bii': 5414
}

DOIT_CONFIG = {
    "default_tasks": ["utc_uv_list_to_csv", "xls_student_data_merge"],
    "verbosity": 2,
    "dep_file": os.path.join(UV_DIR, "../", ".doit.db"),
}
