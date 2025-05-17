Remplacements regex dans une colonne.

Remplace dans la colonne ``colname`` les occurrences de toutes les
expressions régulières renseignées dans ``reps``.

Si l'argument ``backup`` est spécifié, la colonne est sauvegardée
avant toute modification (avec un suffixe ``_orig``). Si
l'argument ``new_colname`` est fourni la colonne est copiée vers
une nouvelle colonne de nom ``new_colname`` et les modifications
sont faites sur cette nouvelle colonne.

Un message ``msg`` peut être spécifié pour décrire ce que fait la
fonction, il sera affiché lorsque l'agrégation sera effectuée.
Sinon, un message générique sera affiché.

Parameters
----------

colname : :obj:`str`
    Nom de la colonne où effectuer les remplacements
*reps : any number of :obj:`tuple`
    Les couples regex / remplacement
new_colname : :obj:`str`
    Le nom de la nouvelle colonne
backup : :obj:`bool`
    Sauvegarder la colonne avant tout changement
msg : :obj:`str`
    Un message décrivant l'opération

Examples
--------

.. code:: python

   DOCS.replace_regex("group", (r"group([0-9])", r"G\1"), (r"g([0-9])", r"G\1"))

