Déclare une agrégation d'un fichier à l'aide d'une fonction.

Fonction générale pour déclarer l'agrégation d'un fichier de
chemin ``filename`` à l'aide d'une fonction ``func`` prenant
en argument le *DataFrame* déjà existant, le chemin vers le
fichier et renvoie le *DataFrame* mis à jour.

Voir fonctions spécialisées pour l'incorporation de documents
classiques :

- :func:`~guv.helpers.Documents.aggregate` : Document csv/Excel
- :func:`~guv.helpers.Documents.aggregate_org` : Document Org

Parameters
----------

filename : :obj:`str`
    Le chemin du fichier à agréger.

func : :obj:`callable`
    Une fonction de signature *DataFrame*, filename: str ->
    *DataFrame* qui réalise l'agrégation.

Examples
--------

.. code:: python

   def fonction_qui_incorpore(df, file_path):
       # On incorpore le fichier dont le chemin est `file_path` au
       # DataFrame `df` et on renvoie le DataFrame mis à jour.

   DOCS.add("documents/notes.csv", func=fonction_qui_incorpore)

