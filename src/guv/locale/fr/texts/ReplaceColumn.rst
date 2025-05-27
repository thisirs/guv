Remplacements dans une colonne.

Remplace les valeurs renseignées dans ``rep_dict`` dans la colonne
``colname``.

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
rep_dict : :obj:`dict`
    Dictionnaire des remplacements
new_colname : :obj:`str`
    Nom de la nouvelle colonne
backup : :obj:`bool`
    Sauvegarder la colonne avant tout changement
msg : :obj:`str`, optional
    Un message décrivant l'opération

Examples
--------

.. code:: python

   DOCS.replace_column("group", {"TD 1": "TD1", "TD 2": "TD2"})

.. code:: python

   ECTS_TO_NUM = {
       "A": 5,
       "B": 4,
       "C": 3,
       "D": 2,
       "E": 1,
       "F": 0
   }
   DOCS.replace_column("Note_TP", ECTS_TO_NUM, backup=True)

