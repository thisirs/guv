"""Fichier de configuration de l'UV"""


# Mode débogage
# DEBUG = "INFO"

from guv.helpers import Documents

DOCS = Documents()

# Chemin relatif vers le fichier Excel de l'effectif issu de l'ENT
# DOCS.add_utc_ent_listing("...")

# Chemin relatif vers les affectations dans les Cours/TD/TP
# DOCS.add_affectation("...")

# Chemin relatif vers le fichier Excel des aménagements
# DOCS.aggregate_amenagements("...")

# Chemin relatif vers le listing provenant de Moodle
# DOCS.add_moodle_listing("...")

# Fichier des changements de Cours
# Il s'agit d'un fichier de prise en compte des changements de groupes
# de Cours. Chaque ligne repère un changement qui est de la forme
# id1 --- id2
# Les identifiants peuvent être des adresses email ou des nom prénom
# DOCS.switch("...", colname="Cours")

# Fichier des changements de TD
# Il s'agit d'un fichier de prise en compte des changements de groupes
# de TD. Chaque ligne repère un changement qui est de la forme
# id1 --- id2
# Les identifiants peuvent être des adresses email ou des nom prénom
# DOCS.switch("...", colname="TD")

# Fichier des changements de TP
# Il s'agit d'un fichier de prise en compte des changements de groupes
# de TP. Chaque ligne repère un changement qui est de la forme
# id1 --- id2
# Les identifiants peuvent être des adresses email ou des nom prénom
# DOCS.switch("...", colname="TP")

# Correspondance entre le noms des groupes de Cours/TD/TP et leur
# identifiant Moodle
MOODLE_GROUPS = None
