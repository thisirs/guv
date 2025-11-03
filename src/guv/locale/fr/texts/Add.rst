Ajoute un fichier au fichier central

Ajoute simplement le fichier si le fichier central n'existe pas encore.
Sinon, utilise la fonction ``func`` pour effectuer l'agrégation.
La fonction ``func`` prend en arguments le *DataFrame* existant et le chemin
vers le fichier, et retourne le *DataFrame* mis à jour.
Des arguments nommés peuvent être passés à ``func`` via ``kw_func``.

Si ``func`` n'est pas fournie, utilise soit ``pd.read_csv`` soit
``pd.read_excel`` en fonction de l'extension du fichier.
Des arguments nommés peuvent être passés à ``pd.read_csv`` ou
``pd.read_excel`` via ``kw_func``.

Voir les fonctions spécialisées pour incorporer des documents standards :

- :func:`~guv.helpers.Documents.aggregate` : Document CSV/Excel
- :func:`~guv.helpers.Documents.aggregate_org` : Document Org

Paramètres
----------

filename : :obj:`str`
    Le chemin vers le fichier à agréger.

func : :obj:`callable`, optionnel
    Une fonction avec la signature *DataFrame*, filename: str ->
    *DataFrame* qui effectue l'agrégation.

kw_func : :obj:`dict`, optionnel
    Arguments nommés à utiliser avec ``func``, ``pd.read_csv`` ou
    ``pd.read_excel``.

Exemples
--------

- Ajout de données lorsqu'il n'y a encore rien :

  .. code:: python

     DOCS.add("documents/base_listing.xlsx")

- Ajout de données lorsqu'il n'y a encore rien, avec des arguments nommés supplémentaires :

  .. code:: python

     DOCS.add("documents/base_listing.xlsx", kw_func={"encoding": "ISO_8859_1"})

- Agrégation en utilisant une fonction :

  .. code:: python

     def function_that_incorporates(df, file_path):
         # Incorpore le fichier à `file_path` dans le DataFrame `df`
         # et retourne le DataFrame mis à jour.

     DOCS.add("documents/notes.csv", func=function_that_incorporates)
