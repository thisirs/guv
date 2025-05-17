Remplace les valeurs non définies dans la colonne ``colname``.

Une seule des options ``na_value`` et ``group_column`` doit être
spécifiée. Si ``na_value`` est spécifiée, on remplace
inconditionnellement par la valeur fournie. Si ``group_column`` est
spécifiée, on complète en groupant par ``group_column`` et en prenant
la seule valeur valide par groupe dans cette colonne.

Parameters
----------

colname : :obj:`str`
    Nom de la colonne où remplacer les ``NA``
na_value : :obj:`str`, optional
    Valeur remplaçant les valeurs non définies
group_column : :obj:`str`, optional
    Nom de la colonne utilisée pour le groupement

Examples
--------

- Mettre les entrées non définies dans la colonne ``note`` à
  "ABS" :

  .. code:: python

     DOCS.fillna_column("note", na_value="ABS")

- Mettre les entrées non définies à l'intérieur de chaque groupe
  repéré par la colonne ``groupe_projet`` à la seule valeur
  définie à l'intérieur de ce groupe.

  .. code:: python

     DOCS.fillna_column("note_projet", group_column="groupe_projet")

