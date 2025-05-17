Réalise des échanges de valeurs dans une colonne.

L'argument ``colname`` est la colonne dans laquelle opérer les
échanges. Si l'argument ``backup`` est spécifié, la colonne est
sauvegardée avant toute modification (avec un suffixe ``_orig``).
Si l'argument ``new_colname`` est fourni la colonne est copiée
vers une nouvelle colonne de nom ``new_colname`` et les
modifications sont faites sur cette nouvelle colonne.

Parameters
----------

filename_or_string : :obj:`str`
    Le chemin du fichier à agréger ou directement le texte du fichier.
colname : :obj:`str`
    Nom de la colonne où opérer les changements
backup : :obj:`bool`
    Sauvegarder la colonne avant tout changement
new_colname : :obj:`str`
    Le nom de la nouvelle colonne

Examples
--------

.. code:: python

   DOCS.switch("fichier_échange_TP", colname="TP")

.. code:: python

   DOCS.switch("Dupont --- Dupond", colname="TP")

