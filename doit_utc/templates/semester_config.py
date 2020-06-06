"""Fichier de configuration du semestre"""


import os
from doit_utc.utils import skip_week, skip_range
from datetime import date

BASE_DIR = os.path.dirname(__file__)

# Fichier pdf de tous les créneaux de toutes les UVs
CRENEAU_UV = os.path.join(BASE_DIR, 'documents', 'Creneaux-UV_P20.pdf')

PLANNINGS = {
    "P2020": {
        "UVS": ["SY09", "SY02"],
        "PL_BEG": date(2020, 2, 24),
        "PL_END": date(2020, 6, 27)
    }
}

SEMESTER = os.path.basename(os.path.dirname(__file__))
SELECTED_UVS = sum((plng['UVS'] for _, plng in PLANNINGS.items()), [])
SELECTED_PLANNINGS = list(PLANNINGS.keys())

DEFAULT_INSTRUCTOR = "Sylvain Rousseau"

# Jours fériés
ferie = [date(2020, 5, 1),
         date(2020, 5, 8),
         date(2020, 5, 21),
         date(2020, 6, 1)]

# Première semaine sans TD/TP
debut = skip_week(PLANNINGS[SEMESTER]['PL_BEG'])

# Semaine des médians
median = skip_range(date(2020, 4, 27), date(2020, 5, 4))

# Vacances
vacances_printemps = skip_range(date(2020, 4, 13), date(2020, 4, 18))

# Semaine des finals
final = skip_range(date(2020, 6, 19), date(2020, 6, 27))

# Jours changés
TURN = {
    date(2020, 5, 4): 'Vendredi',
    date(2020, 5, 12): 'Vendredi',
    date(2020, 5, 20): 'Jeudi',
    date(2020, 6, 4): 'Lundi'
}

# Jours sautés pour Cours/TD/TP
SKIP_DAYS_C = ferie + vacances_printemps + median + final
SKIP_DAYS_D = ferie + vacances_printemps + debut + median + final
SKIP_DAYS_T = ferie + vacances_printemps + debut + final

DOIT_CONFIG = {
    'dep_file': os.path.join(BASE_DIR, '.doit.db'),
    "default_tasks": ["utc_uv_list_to_csv"]
}
