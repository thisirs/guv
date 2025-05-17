Remplace la valeur d'une cellule.

``name_or_email`` est le nom-prénom de l'étudiant ou son adresse
courriel et ``colname`` est le nom de la colonne où faire le
changement. La nouvelle valeur est renseignée par ``value``.

Parameters
----------

name_or_email : :obj:`str`
    Le nom-prénom ou l'adresse courriel de l'étudiant.

colname : :obj:`str`
    Le nom de la colonne où faire les modifications.

value :
    La valeur à affecter.

msg : :obj:`str`
    Un message décrivant l'opération

Examples
--------

.. code:: python

   DOCS.apply_cell("Mark Watney", "Note bricolage", 20)

