Création d'une colonne à partir d'autres colonnes.

Les colonnes nécessaires au calcul sont renseignées dans ``cols``.
Au cas où, on voudrait changer la colonne utilisée pour le calcul
sans changer la fonction ``func``, il est possible de fournir un
tuple ``("col" "other_col")`` où ``col`` est le nom utilisé dans
``func`` et ``other_col`` est la vraie colonne utilisée.

La fonction ``func`` qui calcule la nouvelle colonne reçoit une
*Series* Pandas de toutes les valeurs contenues dans les colonnes
spécifiées.

Parameters
----------

*cols : list of :obj:`str`
    Liste des colonnes fournies à la fonction ``func``
func : :obj:`callable`
    Fonction prenant en argument un dictionnaire "nom des
    colonnes/valeurs" et renvoyant une valeur calculée
colname : :obj:`str`
    Nom de la colonne à créer
msg : :obj:`str`, optional
    Un message décrivant l'opération

Examples
--------

- Moyenne pondérée de deux notes :

  .. code:: python

     def moyenne(notes):
         return .4 * notes["Note_médian"] + .6 * notes["Note_final"]

     DOCS.compute_new_column("Note_médian", "Note_final", func=moyenne, colname="Note_moyenne")

- Moyenne sans tenir compte des valeurs non définies :

  .. code:: python

     def moyenne(notes):
         return notes.mean()

     DOCS.compute_new_column("note1", "note2", "note3", func=moyenne, colname="Note_moyenne")

- Recalcul avec une note modifiée sans redéfinir la function ``moyenne`` :

  .. code:: python

     DOCS.compute_new_column(
         ("note1", "note1_fix"), "note2", "note3", func=moyenne, colname="Note_moyenne (fix)"
     )

