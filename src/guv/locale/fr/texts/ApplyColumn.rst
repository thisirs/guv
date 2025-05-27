Modifie une colonne existante avec une fonction.

``colname`` est un nom de colonne existant et ``func`` une fonction
prenant en argument un élément de la colonne et retournant un
élément modifié.

Un message ``msg`` peut être spécifié pour décrire ce que fait la
fonction, il sera affiché lorsque l'agrégation sera effectuée.
Sinon, un message générique sera affiché.

Parameters
----------

colname : :obj:`str`
    Nom de la colonne où effectuer les remplacements
func : :obj:`callable`
    Fonction prenant en argument un élément et renvoyant l'élément
    modifié
msg : :obj:`str`, optional
    Un message décrivant l'opération

Examples
--------

.. code:: python

   DOCS.apply("note", lambda e: float(str(e).replace(",", ".")))

