"""Fichier de configuration de l'UV"""


# Mode déboguage
# DEBUG = "INFO"

# Chemin relatif vers l'extraction de l'effectif issu de l'ENT
ENT_LISTING = None

# Chemin relatif vers les affectations dans les Cours/TD/TP
AFFECTATION_LISTING = None

# Chemin relatif vers le listing provenant de Moodle
MOODLE_LISTING = None

# Documents supplémentaires à agréger au fichier Excel de l'effectif
# de l'UV. C'est une liste de couples. Chaque couple est composé du
# chemin du fichier à agréger et d'une fonction qui réalise
# l'agrégation. Cette fonction prend en argument un DataFrame existant
# ainsi que le chemin du fichier à agréger et renvoie le DataFrame mis
# à jour. Plusieurs fonctions d'aide sont disponibles: aggregate,
# aggregate_org, fillna_column, replace_regex, replace_column.

from guv.helpers import aggregate

AGGREGATE_DOCUMENTS = None

# Chemin relatif vers le fichier des tiers-temps
# Il s'agit d'une liste d'édudiants, un par ligne bénéficiant d'un
# tiers temps.
TIERS_TEMPS = None

# Fichier des changements de Cours
# Il s'agit d'un fichier de prise en compte des changements de groupes
# de Cours. Chaque ligne repère un changement qui est de la forme
# id1 --- id2
# Les identifiants peuvent être des adresses email ou des nom prénom
CHANGEMENT_COURS = None

# Fichier des changements de TD
# Il s'agit d'un fichier de prise en compte des changements de groupes
# de TD. Chaque ligne repère un changement qui est de la forme
# id1 --- id2
# Les identifiants peuvent être des adresses email ou des nom prénom
CHANGEMENT_TD = None

# Fichier des changements de TP
# Il s'agit d'un fichier de prise en compte des changements de groupes
# de TP. Chaque ligne repère un changement qui est de la forme
# id1 --- id2
# Les identifiants peuvent être des adresses email ou des nom prénom
CHANGEMENT_TP = None

# Fichier contenant des informations supplémentaires sous forme de
# texte libre par étudiant
# C'est fichier au format "org" avec la structure suivante :
# * Jo Crisse
#   blah foo bar
INFO_ETUDIANT = None

# Correspondance entre le noms des groupes de Cours/TD/TP et leur
# identifiant Moodle
MOODLE_GROUPS = None
