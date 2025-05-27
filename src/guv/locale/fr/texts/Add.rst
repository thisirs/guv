Ajoute un fichier au fichier central

Ajoute simplement le fichier s'il n'y a pas encore de fichier central. Sinon
utilise la fonction ``func`` pour réaliser l'agrégation. La fonction ``func``
prend en argument le *DataFrame* déjà existant, le chemin vers le fichier et
renvoie le *DataFrame* mis à jour.

Voir fonctions spécialisées pour l'incorporation de documents classiques :

- :func:`~guv.helpers.Documents.aggregate` : Document csv/Excel
- :func:`~guv.helpers.Documents.aggregate_org` : Document Org

Parameters
----------

filename : :obj:`str`
    Le chemin du fichier à agréger.

func : :obj:`callable`, optional
    Une fonction de signature *DataFrame*, filename: str ->
    *DataFrame* qui réalise l'agrégation.

Examples
--------

- Agrégation en utilisant une fonction :

  .. code:: python

     DOCS.add("documents/liste_de_base.xlsx)

- Agrégation en utilisant une fonction :

  .. code:: python

     def fonction_qui_incorpore(df, file_path):
         # On incorpore le fichier dont le chemin est `file_path` au
         # DataFrame `df` et on renvoie le DataFrame mis à jour.

     DOCS.add("documents/notes.csv", func=fonction_qui_incorpore)

