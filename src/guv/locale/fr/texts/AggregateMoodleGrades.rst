Agrège des feuilles de notes provenant de Moodle.

La feuille de notes doit être un export d'une ou plusieurs notes du carnet
de notes de Moodle sous la forme d'un fichier Excel ou csv.

Les colonnes inutiles seront éliminées. Un renommage des colonnes peut être
effectué en renseignant ``rename``.

Parameters
----------

filename : :obj:`str`
    Le chemin du fichier à agréger.

rename : :obj:`dict`, optional
    Permet de renommer des colonnes après incorporation.

Examples
--------

.. code:: python

   DOCS.aggregate_moodle_grades("documents/SY02 Notes.xlsx")

