"""Fichier de configuration du semestre"""

# Sous-dossiers représentant les UV gérées lors du semestre
UVS = ({{ UVS }})

# Un dictionnaire listant des plannings (A2020, Master2Sem1,
# Master2Sem2...) et leurs caractéristiques correspondantes (UV en
# faisant partie, début et fin...)
from datetime import date
PLANNINGS = {
    "P2020": {
        "UVS": ["SY09", "SY02"],
        "PL_BEG": date(2020, 2, 24),
        "PL_END": date(2020, 6, 27)
    }
}

# Personne par défaut pour les fichier iCal et les calendrier
DEFAULT_INSTRUCTOR = "Sylvain Rousseau"

# Chemin relatif vers le fichier pdf de tous les créneaux de toutes
# les UVs
CRENEAU_UV = "documents/Creneaux-UV_P20.pdf"

SELECTED_PLANNINGS = list(PLANNINGS.keys())


# Information pour l'élaboration du planning du semestre: jours
# fériés, jours changés en d'autres... Il faut renseigner les
# variables TURN, SKIP_DAYS_C, SKIP_DAYS_D et SKIP_DAYS_T

# La variable TURN contient un dictionnaire des journées qui sont
# changées en d'autres jours
TURN = {
    date(2020, 5, 4): 'Vendredi',
    date(2020, 5, 12): 'Vendredi',
    date(2020, 5, 20): 'Jeudi',
    date(2020, 6, 4): 'Lundi'
}


from doit_utc.utils import skip_week, skip_range

# Jours fériés
ferie = [date(2020, 5, 1),
         date(2020, 5, 8),
         date(2020, 5, 21),
         date(2020, 6, 1)]

# Première semaine sans TD/TP
debut = skip_week(PLANNINGS["P2020"]['PL_BEG'])

# Semaine des médians
median = skip_range(date(2020, 4, 27), date(2020, 5, 4))

# Vacances
vacances_printemps = skip_range(date(2020, 4, 13), date(2020, 4, 18))

# Semaine des finals
final = skip_range(date(2020, 6, 19), date(2020, 6, 27))

# Liste des journées où il n'y a pas Cours/TD/TP
SKIP_DAYS_C = ferie + vacances_printemps + median + final
SKIP_DAYS_D = ferie + vacances_printemps + debut + median + final
SKIP_DAYS_T = ferie + vacances_printemps + debut + final
