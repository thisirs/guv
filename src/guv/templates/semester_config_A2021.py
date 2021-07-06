"""Fichier de configuration du semestre"""


# Chemin relatif vers le fichier pdf de tous les créneaux et de toutes
# les UVs disponible sur l'ENT
CRENEAU_UV = None

# Sous-dossiers représentant les UV gérées lors du semestre
UVS = [{{ UVS }}]

# Un dictionnaire listant des plannings (A2020, Master2Sem1,
# Master2Sem2...) et leurs caractéristiques correspondantes (UV en
# faisant partie, début et fin...)
# Par exemple :
# from datetime import date
# PLANNINGS = {
#     "P2020": {
#         "UVS": ["SY09", "SY02"],
#         "PL_BEG": date(2020, 2, 24),
#         "PL_END": date(2020, 6, 27)
#     }
# }
from datetime import date
PLANNINGS = {
    "{{ SEMESTER }}": {
        "UVS": [{{ UVS }}],
        "PL_BEG": date(2021, 5, 6),
        "PL_END": date(2022, 1, 15)
    }
}

# Liste des plannings activés
SELECTED_PLANNINGS = ["{{ SEMESTER }}"]

# Personne par défaut pour les fichiers iCal et les calendriers
DEFAULT_INSTRUCTOR = None

# Informations pour l'élaboration du planning du semestre: jours
# fériés, jours changés en d'autres... Il faut renseigner les
# variables TURN, SKIP_DAYS_C, SKIP_DAYS_D et SKIP_DAYS_T

# La variable TURN contient un dictionnaire des journées qui sont
# changées en d'autres jours :
# Par exemple :
# TURN = {
#   date(2020, 5, 4): "Vendredi"
# }
# Le 4 mai 2020 est transformé en vendredi
TURN = {
    date(2021, 11, 2): "Jeudi",
    date(2021, 11, 10): "Jeudi",
    date(2021, 12, 23): "Samedi"
}

# Liste des journées où il n'y a pas Cours/TD/TP. Le plus simple est
# d'utiliser des variables intermédiaires telles que `ferie` pour
# lister les jours fériés, `median` et `final` pour les semaines
# d'examens ou `debut` pour la première semaine du semestre où il n'y
# a ni TD ni TP. On peut utiliser les fonctions `skip_week` et
# `skip_range`. Par exemple :
# from guv.helpers import skip_week, skip_range
# debut = skip_week(PLANNINGS["P2020"]['PL_BEG'])
# median = skip_range(date(2020, 4, 27), date(2020, 5, 4))
# final = skip_range(date(2020, 6, 19), date(2020, 6, 27))
# ferie = [date(2020, 5, 1),
#          date(2020, 5, 8),
#          date(2020, 5, 21),
#          date(2020, 6, 1)]
# vacances_printemps = skip_range(date(2020, 4, 13), date(2020, 4, 18))
# On définit alors
# SKIP_DAYS_C = ferie + vacances_printemps + median + final
# SKIP_DAYS_D = ferie + vacances_printemps + debut + median + final
# SKIP_DAYS_T = ferie + vacances_printemps + debut + final
from guv.helpers import skip_week, skip_range
debut = skip_week(PLANNINGS["A2021"]['PL_BEG'])
median = skip_range(date(2021, 11, 3), date(2021, 11, 9))
final = skip_range(date(2022, 1, 8), date(2022, 1, 15))
ferie = [
    date(2021, 10, 21),
    date(2021, 11, 11),
]
vacances_noel = skip_range(date(2021, 12, 23), date(2021, 1, 2))
vacances_toussaint = skip_range(date(2021, 10, 25), date(2021, 11, 1))

SKIP_DAYS_C = ferie + vacances_toussaint + vacances_noel + median + final
SKIP_DAYS_D = ferie + vacances_toussaint + vacances_noel + debut + median + final
SKIP_DAYS_T = ferie + vacances_toussaint + vacances_noel + debut + final
